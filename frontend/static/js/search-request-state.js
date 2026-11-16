(function (root, factory) {
  const api = { create: factory };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.UniSportSearchState = api;
})(globalThis, function createSearchState() {
  let requestVersion = 0;
  let initialized = false;
  let resetBeforeInitialization = false;

  function invalidate() {
    requestVersion += 1;
  }

  return {
    async run(request, onSuccess, onError) {
      const version = ++requestVersion;
      try {
        const result = await request();
        if (version === requestVersion) onSuccess(result);
      } catch (error) {
        if (version === requestVersion) onError(error);
      }
    },
    reset() {
      if (!initialized) resetBeforeInitialization = true;
      invalidate();
    },
    markInitialized() {
      initialized = true;
    },
    shouldApplyInitialFilters() {
      return !resetBeforeInitialization;
    },
    initialPage(page) {
      return resetBeforeInitialization ? 1 : page;
    },
  };
});
