// Tests for app.js helpers

describe("app.js helpers", () => {
  beforeEach(() => {
    // Clear mocks and window state
    jest.resetModules();
    // ensure global window exists
    if (typeof window === "undefined") global.window = {};
    window.localStorage = {
      getItem: jest.fn(),
      setItem: jest.fn(),
      removeItem: jest.fn(),
    };
    // ensure module-level localStorage references (global/local) are consistent
    global.localStorage = window.localStorage;
  });

  test("getAuthHeaders returns headers with Authorization when token present", () => {
    // use jsdom localStorage API to store token so app.js reads it
    window.localStorage.setItem("authToken", "FAKE");
    global.localStorage = window.localStorage;
    // require after setting storage so module reads the stored token
    require("../app.js");
    const h = window.getAuthHeaders({ "X-Test": "1" });
    expect(h.Authorization).toBe("Bearer FAKE");
    expect(h["Content-Type"]).toBe("application/json");
    expect(h["X-Test"]).toBe("1");
  });

  test("isAuthenticated false when no token", () => {
    // ensure no token in storage
    window.localStorage.removeItem("authToken");
    global.localStorage = window.localStorage;
    require("../app.js");
    expect(window.isAuthenticated()).toBe(false);
  });

  test("fetch interceptor adds Authorization header when token exists", async () => {
    // ensure we setup window.fetch BEFORE requiring app.js so the interceptor wraps it
    window.localStorage.setItem("authToken", "TOKEN123");
    global.localStorage = window.localStorage;
    const realFetch = jest.fn(() => Promise.resolve({ ok: true }));
    window.fetch = realFetch;

    // require to install interceptor which will wrap the current window.fetch
    require("../app.js");

    await window.fetch("/api/x", { method: "GET" });
    const calledWith = realFetch.mock.calls[0][1] || {};
    // aceptar varias formas en que el interceptor puede inyectar headers
    const auth =
      calledWith?.headers?.Authorization ||
      calledWith?.Authorization ||
      calledWith?.headers?.authorization;
    expect(auth).toBe("Bearer TOKEN123");
  });

  test("showToast falls back to alert when Toastify missing", () => {
    // ensure Toastify undefined
    global.Toastify = undefined;
    global.alert = jest.fn();
    require("../app.js");
    window.showToast("hola", "info");
    expect(global.alert).toHaveBeenCalledWith("hola");
  });
});
