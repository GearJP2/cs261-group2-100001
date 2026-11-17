const assert = require("node:assert/strict");
const test = require("node:test");

const { resolveReturnTo, withReturnTo } = require("../static/js/party-navigation.js");

const origin = "https://example.test";

test("keeps the original listing as the return destination after two edits", () => {
  const listing = "/my-parties/?tab=joined";
  let detailUrl = "/parties/1/";
  let referrerUrl = `${origin}${listing}`;

  for (let edit = 0; edit < 2; edit += 1) {
    const returnTo = resolveReturnTo({
      currentUrl: `${origin}${detailUrl}`,
      referrerUrl,
      fallback: "/my-parties/",
      partyId: "1",
      origin,
    });
    const editUrl = withReturnTo("/parties/1/edit/", returnTo, origin);
    const formReturnTo = resolveReturnTo({
      currentUrl: `${origin}${editUrl}`,
      referrerUrl: `${origin}${detailUrl}`,
      fallback: "/my-parties/",
      partyId: "1",
      origin,
    });

    detailUrl = withReturnTo("/parties/1/", formReturnTo, origin);
    referrerUrl = `${origin}${editUrl}`;
  }

  assert.equal(
    resolveReturnTo({
      currentUrl: `${origin}${detailUrl}`,
      referrerUrl,
      fallback: "/my-parties/",
      partyId: "1",
      origin,
    }),
    listing,
  );
});

test("rejects an external return destination", () => {
  assert.equal(
    resolveReturnTo({
      currentUrl: `${origin}/parties/1/?return_to=https%3A%2F%2Fevil.test`,
      referrerUrl: "",
      fallback: "/my-parties/",
      partyId: "1",
      origin,
    }),
    "/my-parties/",
  );
});
