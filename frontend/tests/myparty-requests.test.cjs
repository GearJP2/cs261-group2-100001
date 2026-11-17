"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

// ดึงเฉพาะโค้ดใน <script> ท้ายไฟล์ myparty.html มาทดสอบโดยไม่แตะ DB/HTTP จริง
const htmlPath = path.resolve(__dirname, "../templates/myparty.html");
const htmlContent = fs.readFileSync(htmlPath, "utf8");
const scriptMatch = htmlContent.match(/<script>([\s\S]*?)<\/script>/);
const scriptSource = scriptMatch ? scriptMatch[1] : "";

function createEnvironment(fetchMock, refreshMembers = async () => ({ status: "loaded" })) {
  const containers = {};
  let reloadCount = 0;
  const scheduledCallbacks = [];

  const document = {
    cookie: "csrftoken=test-csrf-token",
    addEventListener() {},
    querySelectorAll() {
      return [];
    },
    getElementById(id) {
      if (!containers[id]) {
        containers[id] = { id, innerHTML: "" };
      }
      return containers[id];
    },
  };

  const window = {
    PartyMembers: { refresh: refreshMembers },
    location: {
      reload() {
        reloadCount++;
      },
    },
  };

  const context = {
    document,
    window,
    location: window.location,
    fetch: fetchMock,
    setTimeout(fn) {
      scheduledCallbacks.push(fn);
      return scheduledCallbacks.length;
    },
  };

  vm.runInNewContext(scriptSource, context);

  return {
    context,
    containers,
    getReloadCount: () => reloadCount,
    flushTimers: () => scheduledCallbacks.forEach((fn) => fn()),
  };
}

function createActionButton(partyId = "10", requestId = "99") {
  const actionContainer = { innerHTML: "" };
  let clicks = 0;

  const button = {
    parentElement: actionContainer,
    getAttribute(attr) {
      if (attr === "data-party-id") return String(partyId);
      if (attr === "data-request-id") return String(requestId);
      return null;
    },
    // จำลองการคลิกบน DOM จริง: ถ้าถูกแทนที่ด้วยปุ่ม disabled แล้วจะกดซ้ำไม่ได้
    click(handleAction, action) {
      if (actionContainer.innerHTML.includes("disabled")) {
        return;
      }
      clicks++;
      return handleAction(this, action);
    },
    getClicks: () => clicks,
  };

  return { button, actionContainer };
}

// UT-US10-UI-01: ขณะส่ง Approve/Reject -> ปุ่ม disabled และ click ซ้ำไม่เรียก handler เพิ่ม
test("UT-US10-UI-01: disables button immediately while request is in-flight and prevents duplicate calls", async () => {
  let resolveFetch;
  let apiCalls = 0;

  const env = createEnvironment(() => {
    apiCalls++;
    return new Promise((resolve) => {
      resolveFetch = resolve;
    });
  });

  const { button, actionContainer } = createActionButton("10", "501");

  // กดคลิกครั้งแรก (สถานะกำลังส่ง API)
  const pendingPromise = button.click(env.context.handleAction, "approve");

  // ปุ่มต้องเปลี่ยนเป็น disabled ทันทีขณะรอ API
  assert.ok(actionContainer.innerHTML.includes("disabled"));
  assert.ok(actionContainer.innerHTML.includes("กำลังดำเนินการ..."));

  // พยายามกดคลิกซ้ำขณะยังส่งไม่เสร็จ -> ต้องไม่เรียก handler หรือยิง API เพิ่ม
  button.click(env.context.handleAction, "approve");
  assert.equal(apiCalls, 1);

  resolveFetch({ ok: true, status: 200, json: async () => ({}) });
  await pendingPromise;
});

// UT-US10-UI-02: Approve สำเร็จจาก mocked API -> แสดงสถานะอนุมัติและสั่ง refresh ข้อมูลคำขอ สมาชิก และที่ว่าง
test("UT-US10-UI-02: successful Approve sends Approved status, updates state, and triggers refresh", async () => {
  let capturedUrl = null;
  let capturedOptions = null;

  const env = createEnvironment(async (url, options) => {
    capturedUrl = url;
    capturedOptions = options;
    return { ok: true, status: 200, json: async () => ({}) };
  });

  const { button, actionContainer } = createActionButton("12", "301");
  await env.context.handleAction(button, "approve");

  assert.equal(capturedUrl, "/api/v1/parties/12/join-requests/301/decision");
  assert.equal(capturedOptions.method, "POST");
  assert.equal(capturedOptions.headers["X-CSRFToken"], "test-csrf-token");
  assert.deepEqual(JSON.parse(capturedOptions.body), { status: "Approved" });
  assert.ok(actionContainer.innerHTML.includes("เป็นสมาชิกแล้ว"));
  assert.ok(actionContainer.innerHTML.includes("disabled"));

  // ตรวจสอบการ trigger reload เพื่อรีเฟรชคำขอ สมาชิก และที่ว่าง
  env.flushTimers();
  assert.equal(env.getReloadCount(), 1);
});

// UT-US10-UI-03: Reject สำเร็จจาก mocked API -> ลบ Pending จากรายการโดยไม่แสดงว่าเพิ่มสมาชิก
test("UT-US10-UI-03: successful Reject sends Rejected status and refreshes without adding member", async () => {
  let capturedBody = null;

  const env = createEnvironment(async (_url, options) => {
    capturedBody = JSON.parse(options.body);
    return { ok: true, status: 200, json: async () => ({}) };
  });

  const { button, actionContainer } = createActionButton("12", "302");
  await env.context.handleAction(button, "reject");

  assert.deepEqual(capturedBody, { status: "Rejected" });
  assert.ok(actionContainer.innerHTML.includes("ปฏิเสธคำขอ"));
  assert.ok(!actionContainer.innerHTML.includes("เป็นสมาชิกแล้ว"));

  env.flushTimers();
  assert.equal(env.getReloadCount(), 1);
});

// UT-US10-UI-04: API error/empty/loading -> render state ถูกต้องและไม่แสดงสำเร็จปลอม
test("UT-US10-UI-04: renders empty, error, and action failure states accurately without false success", async () => {
  // 1. ทดสอบกรณี Empty (ไม่มีคำขอที่รออนุมัติ)
  const emptyEnv = createEnvironment(async () => ({
    ok: true,
    status: 200,
    json: async () => ({ data: [] }),
  }));
  await emptyEnv.context.loadRequests("20");
  assert.ok(emptyEnv.containers["req-list-20"].innerHTML.includes("ไม่มีคำขอที่รออนุมัติ"));

  // 2. ทดสอบกรณี Load Pending API Error (เช่น 500 หรือไม่มีสิทธิ์ 403)
  const loadErrEnv = createEnvironment(async () => ({
    ok: false,
    status: 500,
  }));
  await loadErrEnv.context.loadRequests("21");
  assert.ok(loadErrEnv.containers["req-list-21"].innerHTML.includes("ไม่สามารถดึงข้อมูลคำขอได้"));

  // 3. ทดสอบกรณี Action API Error (เช่น ปาร์ตี้เต็ม/เริ่มแล้ว/ยกเลิก/ผู้ไม่มีสิทธิ์ ตอบกลับ 400/403/409/500)
  const actionErrEnv = createEnvironment(async () => ({
    ok: false,
    status: 409,
  }));
  const { button, actionContainer } = createActionButton("22", "401");
  await actionErrEnv.context.handleAction(button, "approve");

  assert.ok(actionContainer.innerHTML.includes("ไม่สามารถดำเนินการได้"));
  assert.ok(!actionContainer.innerHTML.includes("เป็นสมาชิกแล้ว"));
  assert.ok(!actionContainer.innerHTML.includes("ปฏิเสธคำขอ"));
  actionErrEnv.flushTimers();
  assert.equal(actionErrEnv.getReloadCount(), 0);
});

test("escapes pending applicant names rather than inserting HTML", async () => {
  const env = createEnvironment(async () => ({
    ok: true,
    json: async () => ({ data: [{ id: 7, display_name: '<img src=x onerror="alert(1)">', level: '<script>alert(1)</script>' }] }),
  }));
  await env.context.loadRequests("20");
  const output = env.containers["req-list-20"].innerHTML;
  assert.ok(output.includes("&lt;img"));
  assert.ok(output.includes("&lt;script&gt;"));
  assert.ok(!output.includes("<img"));
  assert.ok(!output.includes("<script"));
});
