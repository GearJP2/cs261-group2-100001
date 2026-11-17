(function (root, factory) {
  "use strict";

  const navigation = factory();
  if (typeof module === "object" && module.exports) module.exports = navigation;
  if (root) root.PartyNavigation = navigation;
})(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";

  function localPath(value, origin) {
    if (typeof value !== "string" || !value.trim()) return null;
    try {
      const url = new URL(value, origin);
      if (url.origin !== origin || url.username || url.password) return null;
      return `${url.pathname}${url.search}${url.hash}`;
    } catch (error) {
      if (error instanceof TypeError) return null;
      throw error;
    }
  }

  function resolveReturnTo({ currentUrl, referrerUrl, fallback, partyId, origin }) {
    const editPath = `/parties/${partyId}/edit/`;
    const current = new URL(currentUrl, origin);
    const explicit = localPath(current.searchParams.get("return_to"), origin);
    if (explicit && new URL(explicit, origin).pathname !== editPath) return explicit;

    if (referrerUrl) {
      const referrer = new URL(referrerUrl, origin);
      if (referrer.origin === origin && referrer.pathname !== editPath) {
        const path = localPath(referrer.href, origin);
        if (path) return path;
      }
    }

    const fallbackPath = localPath(fallback, origin);
    return fallbackPath && new URL(fallbackPath, origin).pathname !== editPath
      ? fallbackPath
      : "/";
  }

  function withReturnTo(path, returnTo, origin) {
    const destination = new URL(path, origin);
    if (destination.origin !== origin) {
      throw new TypeError("Party navigation destination must be same-origin");
    }
    const localReturnTo = localPath(returnTo, origin);
    if (!localReturnTo) throw new TypeError("Party return destination must be same-origin");
    destination.searchParams.set("return_to", localReturnTo);
    return `${destination.pathname}${destination.search}${destination.hash}`;
  }

  return { resolveReturnTo, withReturnTo };
});
