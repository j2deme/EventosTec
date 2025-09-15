// Utilities for tests: mockFetch factory and localStorage helpers
function mockFetchFactory(mapping = {}) {
  return jest.fn((url, init) => {
    for (const pattern of Object.keys(mapping)) {
      if (url.startsWith(pattern)) {
        const resp = mapping[pattern];
        if (typeof resp === "function") return Promise.resolve(resp(url, init));
        return Promise.resolve(resp);
      }
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
  });
}

function setupLocalStorage(items = {}) {
  window.localStorage.clear();
  Object.keys(items).forEach((k) => window.localStorage.setItem(k, items[k]));
}

module.exports = {
  mockFetchFactory,
  setupLocalStorage,
};
