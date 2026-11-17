"use strict";

const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(require.resolve("../static/js/party-members.js"), "utf8");

function node(dataset = {}) {
  return {
    dataset,
    children: [],
    hidden: false,
    textContent: "",
    events: {},
    replaceChildren(...children) { this.children = children; },
    append(...children) { this.children.push(...children); },
    addEventListener(name, handler) { this.events[name] = handler; },
    click() { return this.events.click?.(); },
    querySelector(selector) { return this.nodes[selector] || null; },
  };
}

function fixture(request) {
  const list = node();
  const count = node();
  const status = node();
  const retry = node();
  const panel = node({ partyMembers: "12", partyCapacity: "4" });
  panel.nodes = {
    "[data-member-list]": list,
    "[data-member-count]": count,
    "[data-member-status]": status,
    "[data-member-retry]": retry,
    "[data-remaining-slots]": node(),
  };
  list.children = [node()];
  const remaining = panel.nodes["[data-remaining-slots]"];
  const redirects = [];
  const document = {
    querySelectorAll: () => [panel],
    createElement: () => node(),
    addEventListener() {},
  };
  const window = {
    UniSport: { request },
    location: { replace: (path) => redirects.push(path) },
  };
  vm.runInNewContext(source, { document, window });
  return { window, panel, list, count, status, retry, remaining, redirects };
}

test("renders only the API members and uses its Party-matching count", async () => {
  const calls = [];
  const f = fixture(async (path) => {
    calls.push(path);
    return {
      members: [
        { user_id: 1, display_name: "Host", role: "Host" },
        { user_id: 2, display_name: "Member", role: "Member" },
      ],
      member_count: 2,
    };
  });

  const result = await f.window.PartyMembers.refresh("12");

  assert.deepEqual(calls, ["/parties/12/members"]);
  assert.equal(result.status, "loaded");
  assert.equal(f.count.textContent, "2");
  assert.equal(f.remaining.textContent, "2");
  assert.deepEqual(f.list.children.map((row) => row.children[0].textContent), ["Host", "Member"]);
  assert.deepEqual(f.list.children.map((row) => row.children[1].textContent), ["ผู้จัด", "สมาชิก"]);
});

test("clears stale members when a just-withdrawn user is forbidden", async () => {
  const f = fixture(async () => { throw Object.assign(new Error("Forbidden"), { status: 403 }); });

  const result = await f.window.PartyMembers.refresh("12");

  assert.equal(result.status, "forbidden");
  assert.deepEqual(f.list.children, []);
  assert.match(f.status.textContent, /ผู้จัดหรือสมาชิกปัจจุบัน/);
  assert.equal(f.retry.hidden, true);
});

test("refresh after approval replaces the count and member list", async () => {
  let approved = false;
  const f = fixture(async () => approved
    ? {
      members: [
        { user_id: 1, display_name: "Host", role: "Host" },
        { user_id: 2, display_name: "New member", role: "Member" },
      ],
      member_count: 2,
    }
    : {
      members: [{ user_id: 1, display_name: "Host", role: "Host" }],
      member_count: 1,
    });

  await f.window.PartyMembers.refresh("12");
  approved = true;
  const result = await f.window.PartyMembers.refresh("12");

  assert.equal(result.memberCount, 2);
  assert.equal(f.count.textContent, "2");
  assert.deepEqual(f.list.children.map((row) => row.children[0].textContent), ["Host", "New member"]);
});

test("rejects a response whose count disagrees with its member list", async () => {
  const f = fixture(async () => ({
    members: [{ user_id: 1, display_name: "Host", role: "Host" }],
    member_count: 2,
  }));

  const result = await f.window.PartyMembers.refresh("12");

  assert.equal(result.status, "error");
  assert.deepEqual(f.list.children, []);
  assert.equal(f.retry.hidden, false);
  assert.match(f.status.textContent, /โหลดรายชื่อสมาชิกไม่สำเร็จ/);
});

test("UT-US6-UI-02: renders the API fallback name without requiring an avatar", async () => {
  const f = fixture(async () => ({members: [{user_id: 2, display_name: "ผู้ใช้", role: "Member"}], member_count: 1}));
  await f.window.PartyMembers.refresh("12");
  assert.equal(f.list.children[0].children[0].textContent, "ผู้ใช้");
  assert.equal(f.list.children[0].children[1].textContent, "สมาชิก");
});

test("UT-US6-UI-03: loading clears stale rows then renders a genuine empty result", async () => {
  let finish;
  const f = fixture(() => new Promise(resolve => { finish = resolve; }));
  const pending = f.window.PartyMembers.refresh("12");
  assert.deepEqual(f.list.children, []);
  assert.match(f.status.textContent, /กำลังโหลด/);
  finish({members: [], member_count: 0});
  await pending;
  assert.equal(f.count.textContent, "0");
  assert.match(f.status.textContent, /ยังไม่มีสมาชิก/);
  assert.equal(f.retry.hidden, true);
});

test("UT-US6-UI-03: not found clears stale rows and retry loads the next real input", async () => {
  let calls = 0;
  const f = fixture(async () => {
    if (++calls === 1) throw Object.assign(new Error("Missing"), {status: 404});
    return {members: [], member_count: 0};
  });
  assert.equal((await f.window.PartyMembers.refresh("12")).status, "error");
  assert.deepEqual(f.list.children, []);
  assert.equal(f.retry.hidden, false);
  await f.retry.click();
  assert.equal(calls, 2);
  assert.equal(f.retry.hidden, true);
});
