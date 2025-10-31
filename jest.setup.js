// Global Jest setup for jsdom environment
// Provides minimal mocks for fetch, safeFetch, localStorage, alert, confirm,
// Toastify and window.showToast used throughout frontend modules.

// Mock fetch to a controllable function. Tests can override global.fetch
// per-suite if they need custom responses.
if (typeof global.fetch !== "function") {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
  );
}

// Ensure window.fetch and window.safeFetch delegate to the current global.fetch
// so tests that reassign `global.fetch = jest.fn()` are observed by modules
if (typeof window !== "undefined") {
  // proxying wrapper keeps reference to latest global.fetch
  window.fetch = (...args) => global.fetch(...args);
  window.safeFetch = (...args) => global.fetch(...args);
}

// Make global.safeFetch point to global.fetch by default as well
global.safeFetch = (...args) => global.fetch(...args);

// Minimal localStorage mock for jsdom
if (
  typeof window !== "undefined" &&
  typeof window.localStorage === "undefined"
) {
  const store = {};
  window.localStorage = {
    getItem: (key) =>
      Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null,
    setItem: (key, value) => {
      store[key] = String(value);
    },
    removeItem: (key) => {
      delete store[key];
    },
    clear: () => {
      Object.keys(store).forEach((k) => delete store[k]);
    },
  };
}

// Provide window.alert and window.confirm (jsdom may not implement navigation)
if (typeof window !== "undefined") {
  if (typeof window.alert !== "function") {
    window.alert = jest.fn();
  }
  if (typeof window.confirm !== "function") {
    window.confirm = jest.fn(() => true);
  }
}

// Lightweight Toast/notification mocks used by the app
if (typeof window !== "undefined") {
  // showToast helper used in many modules
  if (typeof window.showToast !== "function") {
    window.showToast = jest.fn((_msg, _type) => {});
  }

  // Some tests or modules expect Toastify global
  if (typeof window.Toastify === "undefined") {
    window.Toastify = {
      // returning an object with "showToast" to mimic usage in codepaths
      // actual Toastify usage is minimal in tests; this prevents crashes
      // when requiring modules that call Toastify.
      show: jest.fn(() => ({ showToast: jest.fn() })),
    };
  }
}

// Silence console.error/info/warn in tests by default to reduce noise
// Tests that assert on console behaviour can still spyOn(console, 'error')
const _origConsoleError = console.error;
const _origConsoleWarn = console.warn;
const _origConsoleInfo = console.info;

beforeEach(() => {
  // Reset fetch mock call history before each test
  if (global.fetch && global.fetch.mockReset) global.fetch.mockReset();
  if (global.safeFetch && global.safeFetch.mockReset)
    global.safeFetch.mockReset && global.safeFetch.mockReset();
  if (typeof window !== "undefined") {
    if (window.showToast && window.showToast.mockReset)
      window.showToast.mockReset();
    if (
      window.Toastify &&
      window.Toastify.show &&
      window.Toastify.show.mockReset
    )
      window.Toastify.show.mockReset();
    // keep window.fetch delegating to global.fetch but reset global.fetch mock
    if (global.fetch && global.fetch.mockReset) global.fetch.mockReset();
  }
});

// Optional: keep console output but prefix it so it's easier to filter in CI logs.
console.error = (...args) => {
  _origConsoleError("[console.error]", ...args);
};
console.warn = (...args) => {
  _origConsoleWarn("[console.warn]", ...args);
};
console.info = (...args) => {
  _origConsoleInfo("[console.info]", ...args);
};
