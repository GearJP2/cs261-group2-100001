const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const scriptPath = path.resolve(__dirname, "../static/js/myparty-review.js");
const scriptSource = fs.readFileSync(scriptPath, "utf8");

function createReviewFixture({
  partyId = "42",
  canReview = true,
  targets = [
    { id: "101", name: "Alice", reviewed: false },
    { id: "102", name: "Bob", reviewed: false },
  ],
  requestMock = async () => ({ status: 201 }),
} = {}) {
  const listeners = new Map();
  const bindEvents = (el) => {
    el._listeners = {};
    el.addEventListener = (type, fn) => {
      el._listeners[type] = el._listeners[type] || [];
      el._listeners[type].push(fn);
    };
    el.dispatch = async (type, eventObj = {}) => {
      const fns = el._listeners[type] || [];
      for (const fn of fns) {
        await fn({
          preventDefault() {
            this.defaultPrevented = true;
          },
          ...eventObj,
        });
      }
    };
    return el;
  };

  const historyHeading = {
    id: "history-heading",
    focused: false,
    focus() {
      this.focused = true;
    },
  };

  const opener = bindEvents({
    disabled: !canReview,
    textContent: canReview ? "ให้คะแนนและรีวิว" : "ไม่มีสมาชิกที่ยังรีวิวได้",
    focused: false,
    focus() {
      this.focused = true;
    },
  });

  const options = [
    { value: "", textContent: "เลือกสมาชิก", disabled: false },
    ...targets.map((t) => ({
      value: String(t.id),
      textContent: t.reviewed ? `${t.name} — รีวิวแล้ว` : t.name,
      disabled: Boolean(t.reviewed),
    })),
  ];

  const targetSelect = {
    value: "",
    disabled: false,
    options,
    get selectedOptions() {
      return this.options.filter((o) => o.value === this.value);
    },
  };

  const ratingRadios = [1, 2, 3, 4, 5].map((n) => ({
    name: "rating",
    value: String(n),
    disabled: false,
    checked: false,
  }));

  const ratingNodeList = {
    value: "",
    forEach(cb) {
      ratingRadios.forEach(cb);
    },
  };

  const commentInput = bindEvents({
    value: "",
    disabled: false,
    customValidity: "",
    setCustomValidity(msg) {
      this.customValidity = msg;
    },
  });

  const countOutput = { textContent: "0" };
  const messageEl = { textContent: "" };
  const closeBtn = bindEvents({ disabled: false });
  const submitBtn = bindEvents({ disabled: !canReview });

  const form = bindEvents({
    elements: {
      reviewee_id: targetSelect,
      comment: commentInput,
      rating: ratingNodeList,
    },
    querySelector(sel) {
      if (sel === '[type="submit"]') return submitBtn;
      return null;
    },
    querySelectorAll(sel) {
      if (sel === '[name="rating"]') return ratingRadios;
      return [];
    },
    reportValidity() {
      if (commentInput.customValidity) return false;
      if (!targetSelect.value || !ratingNodeList.value || !commentInput.value.trim()) {
        return false;
      }
      const chosen = targetSelect.options.find((o) => o.value === targetSelect.value);
      if (!chosen || chosen.disabled) return false;
      return true;
    },
    reset() {
      targetSelect.value = "";
      ratingNodeList.value = "";
      commentInput.value = "";
      commentInput.customValidity = "";
    },
  });

  const dialog = bindEvents({
    id: `review-dialog-${partyId}`,
    dataset: { partyId: String(partyId) },
    open: false,
    showModal() {
      this.open = true;
    },
    close() {
      this.open = false;
      this.dispatch("close");
    },
    querySelector(sel) {
      if (sel === "form") return form;
      if (sel === "[data-review-message]") return messageEl;
      if (sel === "[data-review-close]") return closeBtn;
      if (sel === "[data-review-count]") return countOutput;
      return null;
    },
  });

  const document = {
    querySelectorAll(sel) {
      if (sel === "[data-review-dialog]") return [dialog];
      return [];
    },
    querySelector(sel) {
      if (sel === `[data-open-review="${dialog.id}"]`) return opener;
      return null;
    },
    getElementById(id) {
      if (id === "history-heading") return historyHeading;
      return null;
    },
  };

  const window = {
    UniSport: {
      request: requestMock,
    },
  };

  const context = vm.createContext({
    window,
    document,
    Number,
    String,
    JSON,
  });

  vm.runInContext(scriptSource, context);

  return {
    dialog,
    form,
    opener,
    closeBtn,
    submitBtn,
    targetSelect,
    ratingNodeList,
    ratingRadios,
    commentInput,
    countOutput,
    messageEl,
    historyHeading,
  };
}

test("UT-US14-UI-01: ineligible party or already-reviewed target disables/blocks review submission per policy", async () => {
  let apiCalls = 0;
  const ineligibleEnv = createReviewFixture({
    canReview: false,
    targets: [{ id: "101", name: "Alice", reviewed: true }],
    requestMock: async () => {
      apiCalls++;
    },
  });

  assert.equal(ineligibleEnv.opener.disabled, true);
  assert.equal(ineligibleEnv.opener.textContent, "ไม่มีสมาชิกที่ยังรีวิวได้");
  assert.equal(ineligibleEnv.targetSelect.options[1].disabled, true);

  ineligibleEnv.targetSelect.value = "101";
  ineligibleEnv.ratingNodeList.value = "5";
  ineligibleEnv.commentInput.value = "Great teammate";
  await ineligibleEnv.form.dispatch("submit");
  assert.equal(apiCalls, 0);
});

test("UT-US14-UI-02: invalid rating or whitespace-only comment fails validation, sets error, and prevents submit", async () => {
  let apiCalls = 0;
  const env = createReviewFixture({
    requestMock: async () => {
      apiCalls++;
    },
  });

  env.targetSelect.value = "101";
  env.ratingNodeList.value = "4";
  env.commentInput.value = "   ";

  await env.form.dispatch("submit");

  assert.equal(env.commentInput.customValidity, "กรุณาระบุความคิดเห็น");
  assert.equal(apiCalls, 0);

  env.commentInput.value = "เล่นดีมาก";
  await env.commentInput.dispatch("input");
  assert.equal(env.commentInput.customValidity, "");
  assert.equal(env.countOutput.textContent, String("เล่นดีมาก".length));
});

test("UT-US14-UI-03: in-flight submit disables controls to prevent duplicate calls and updates review/summary state on completion", async () => {
  let resolveRequest;
  const calls = [];
  const env = createReviewFixture({
    partyId: "55",
    targets: [{ id: "101", name: "Alice", reviewed: false }],
    requestMock: (url, options) => {
      calls.push({ url, options });
      return new Promise((resolve) => {
        resolveRequest = resolve;
      });
    },
  });

  env.targetSelect.value = "101";
  env.ratingNodeList.value = "5";
  env.commentInput.value = "  ตรงเวลาและช่วยทีมดีมาก  ";

  const firstSubmit = env.form.dispatch("submit");

  assert.equal(env.submitBtn.disabled, true);
  assert.equal(env.closeBtn.disabled, true);
  assert.equal(env.targetSelect.disabled, true);
  assert.equal(env.commentInput.disabled, true);
  assert.equal(env.messageEl.textContent, "กำลังส่งรีวิว…");

  await env.form.dispatch("submit");
  assert.equal(calls.length, 1);

  resolveRequest({ status: 201 });
  await firstSubmit;

  assert.equal(calls[0].url, "/parties/55/reviews");
  assert.equal(calls[0].options.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    reviewee_id: 101,
    rating: 5,
    comment: "ตรงเวลาและช่วยทีมดีมาก",
  });

  assert.equal(env.targetSelect.options[1].disabled, true);
  assert.ok(env.targetSelect.options[1].textContent.includes("— รีวิวแล้ว"));
  assert.equal(env.messageEl.textContent, "บันทึกรีวิวเรียบร้อยแล้ว");
  assert.equal(env.countOutput.textContent, "0");
  assert.equal(env.submitBtn.disabled, true);
  assert.equal(env.opener.disabled, true);
  assert.equal(env.opener.textContent, "รีวิวสมาชิกครบแล้ว");
});

test("UT-US14-UI-04: handles 409 REVIEW_EXISTS / network error states accurately and keeps star rating separate from conduct credit", async () => {
  const conflictEnv = createReviewFixture({
    targets: [
      { id: "101", name: "Alice", reviewed: false },
      { id: "102", name: "Bob", reviewed: false },
    ],
    requestMock: async () => {
      const err = new Error("คุณได้รีวิวสมาชิกคนนี้ไปแล้ว");
      err.status = 409;
      err.payload = { error: { code: "REVIEW_EXISTS" } };
      throw err;
    },
  });

  conflictEnv.targetSelect.value = "101";
  conflictEnv.ratingNodeList.value = "3";
  conflictEnv.commentInput.value = "Good game";
  await conflictEnv.form.dispatch("submit");

  assert.equal(conflictEnv.targetSelect.options[1].disabled, true);
  assert.ok(conflictEnv.targetSelect.options[1].textContent.includes("— รีวิวแล้ว"));
  assert.equal(conflictEnv.targetSelect.value, "");
  assert.equal(conflictEnv.messageEl.textContent, "คุณได้รีวิวสมาชิกคนนี้ไปแล้ว");
  assert.equal(conflictEnv.opener.disabled, false);

  const netErrEnv = createReviewFixture({
    requestMock: async () => {
      throw new Error("Network failure");
    },
  });

  netErrEnv.targetSelect.value = "101";
  netErrEnv.ratingNodeList.value = "5";
  netErrEnv.commentInput.value = "Good game";
  await netErrEnv.form.dispatch("submit");

  assert.equal(
    netErrEnv.messageEl.textContent,
    "ยังยืนยันผลส่งรีวิวไม่ได้ กรุณาโหลดหน้าใหม่เพื่อตรวจสถานะก่อนส่งอีกครั้ง"
  );

  const tplPath = path.resolve(__dirname, "../templates/partials/review_history_content.html");
  const tpl = fs.readFileSync(tplPath, "utf8");
  assert.ok(tpl.includes("คะแนนดาว (1–5)"));
  assert.ok(tpl.includes("ยังไม่มีกิจกรรมที่จบแล้วซึ่งคุณมีสิทธิ์รีวิว"));
  assert.ok(!tpl.toLowerCase().includes("conduct"));
});
