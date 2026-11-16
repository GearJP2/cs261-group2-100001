"use strict";

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { create } = require("../static/js/search-request-state.js");

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

test("ignores an older successful search after a newer search", async () => {
  const state = create();
  const older = deferred();
  const results = [];

  const olderRequest = state.run(() => older.promise, (result) => results.push(result), assert.fail);
  await state.run(async () => "new", (result) => results.push(result), assert.fail);
  older.resolve("old");
  await olderRequest;

  assert.deepEqual(results, ["new"]);
});

test("ignores an older search error after reset", async () => {
  const state = create();
  const older = deferred();
  const errors = [];

  const olderRequest = state.run(() => older.promise, assert.fail, (error) => errors.push(error));
  state.reset();
  await state.run(async () => "reset results", assert.ok, assert.fail);
  older.reject(new Error("stale error"));
  await olderRequest;

  assert.deepEqual(errors, []);
});

test("surfaces the error from the latest search", async () => {
  const state = create();
  const expectedError = new Error("latest error");
  const errors = [];

  await state.run(
    async () => { throw expectedError; },
    assert.fail,
    (error) => errors.push(error),
  );

  assert.deepEqual(errors, [expectedError]);
});

test("does not restore URL filters or page after reset during initialization", () => {
  const state = create();

  state.reset();

  assert.equal(state.shouldApplyInitialFilters(), false);
  assert.equal(state.initialPage("4"), 1);
  state.markInitialized();
});

test("keeps URL filters and page when initialization was not reset", () => {
  const state = create();

  assert.equal(state.shouldApplyInitialFilters(), true);
  assert.equal(state.initialPage("4"), "4");
});
