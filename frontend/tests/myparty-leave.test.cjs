"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(require.resolve("../static/js/myparty-leave.js"), "utf8");

function node(extra = {}) {
  return Object.assign({
    disabled: false, hidden: false, textContent: "", events: {},
    addEventListener(name, handler) { this.events[name] = handler; },
    click() { if (!this.disabled) return this.events.click?.(); },
    focus() {}, remove() { this.removed = true; },
    replaceChildren() { this.cleared = true; },
    querySelectorAll() { return []; },
  }, extra);
}

function fixture(request) {
  const form = node(), message = node(), close = node(), confirm = node(), refresh = node({ hidden: true });
  const dialogNodes = { form, '[data-leave-message]': message, '[data-leave-close]': close,
    '[data-leave-confirm]': confirm, '[data-leave-refresh]': refresh, '[data-leave-title]': node() };
  const dialog = node({ querySelector: key => dialogNodes[key], showModal() { this.open = true; },
    close() { this.open = false; this.events.close?.(); } });
  const count = node({ textContent: "2" });
  const cards = [node(), node()];
  cards.forEach(card => { card.querySelector = key => key === 'h3' ? node({ textContent: "Party" }) : count; });
  const buttons = cards.map((card, index) => node({ dataset: { leaveParty: String(index + 1) },
    isConnected: true, closest: () => card }));
  const empty = node(), result = node();
  const pane = node({ querySelectorAll: () => buttons,
    querySelector: key => key === '[data-joined-empty]' ? empty : key === '[data-leave-result]' ? result : cards.find(card => !card.removed) });
  const created = node(), history = node(), protectedMembers = node();
  const document = {
    getElementById: key => ({ 'grid-joined': pane, 'leave-dialog': dialog, 'grid-created': created,
      'grid-history': history, 'joined-heading': node() })[key],
    querySelectorAll: key => key.startsWith('[data-joined-party],') ? [...cards, protectedMembers] : [],
    querySelector: () => null,
  };
  const redirects = []; let reloads = 0;
  const memberRefreshes = [];
  vm.runInNewContext(source, { document, window: { UniSport: { request },
    PartyMembers: { refresh: async partyId => {
      memberRefreshes.push(String(partyId));
      return { status: "forbidden" };
    } },
    location: { replace: path => redirects.push(path), reload: () => reloads++ } } });
  return { buttons, cards, created, history, protectedMembers, redirects, refresh, confirm, close, message, dialog,
    memberRefreshes, reloads: () => reloads, submit: () => form.events.submit({ preventDefault() {} }) };
}

for (const status of [500, 409, undefined]) {
  test(`error ${status ?? "network"} offers a refresh without replaying leave`, async () => {
    let calls = 0;
    const f = fixture(async () => { calls++; throw Object.assign(new Error("API error"), { status }); });
    f.buttons[0].click();
    await f.submit();
    assert.equal(f.refresh.hidden, false);
    assert.equal(f.confirm.hidden, true);
    assert.equal(f.buttons[0].disabled, true);
    f.close.click(); f.buttons[0].click();
    assert.equal(calls, 1);
    f.refresh.click();
    assert.equal(f.reloads(), 1);
  });
}

for (const duringDetail of [false, true]) {
  test(`401 ${duringDetail ? "during count refresh" : "during leave"} clears protected data and returns to login`, async () => {
    const f = fixture(async path => {
      if (duringDetail && path.endsWith('/leave')) return {};
      throw Object.assign(new Error("Session expired"), { status: 401 });
    });
    f.buttons[0].click();
    await f.submit();
    assert.ok(f.cards.every(card => card.removed));
    assert.ok(f.protectedMembers.removed);
    assert.ok(f.created.cleared && f.history.cleared);
    assert.deepEqual(f.redirects, ['/login/']);
  });
}

test("403 is scoped to the current Party and does not log out the viewer", async () => {
  const f = fixture(async () => { throw Object.assign(new Error("Forbidden"), { status: 403 }); });
  f.buttons[0].click(); await f.submit();
  assert.equal(f.cards[1].removed, undefined);
  assert.equal(f.buttons[1].disabled, false);
  assert.equal(f.created.cleared, undefined);
  assert.deepEqual(f.redirects, []);
  assert.equal(f.refresh.hidden, false);
});

test("pending request prevents a second submit", async () => {
  let resolve; let calls = 0;
  const f = fixture(path => {
    if (!path.endsWith("/leave")) return Promise.resolve({ member_count: 1, remaining_slots: 2 });
    calls++; return new Promise(done => { resolve = done; });
  });
  f.buttons[0].click(); const pending = f.submit();
  await f.submit();
  assert.equal(calls, 1); assert.equal(f.buttons[0].disabled, true);
  let cancelled = false;
  f.dialog.events.cancel({ preventDefault() { cancelled = true; } });
  assert.equal(cancelled, true);
  resolve({}); await pending;
});

test("refreshes members after a successful leave and treats the expected 403 as normal", async () => {
  const calls = [];
  const f = fixture(async path => {
    calls.push(path);
    if (path.endsWith("/leave")) return {};
    return { member_count: 1, remaining_slots: 6 };
  });

  f.buttons[0].click();
  await f.submit();

  assert.deepEqual(calls, ["/parties/1/leave", "/parties/1"]);
  assert.deepEqual(f.memberRefreshes, ["1"]);
  assert.equal(f.cards[0].removed, true);
  assert.match(f.message.textContent, /ถอนตัวสำเร็จแล้ว สมาชิกปัจจุบัน 1 คน ที่ว่าง 6 ที่/);
  assert.doesNotMatch(f.message.textContent, /โหลดรายชื่อสมาชิกไม่ได้/);
});


test("cancel closes the confirmation dialog without a leave request or card mutation", async () => {
  let calls = 0;
  const f = fixture(async () => { calls++; throw new Error("Cancel must not call API"); });
  f.buttons[0].click();
  assert.equal(f.dialog.open, true);
  f.close.click();
  assert.equal(f.dialog.open, false);
  assert.equal(calls, 0);
  assert.ok(f.cards.every(card => !card.removed));
  assert.equal(f.buttons[0].disabled, false);
  assert.equal(f.message.textContent, "");
});
