// Tests for app.js helpers and global utilities
require("../app"); // load the module to expose window.* helpers

describe("app.js helpers", () => {
  beforeEach(() => {
    window.localStorage.clear();
    delete global.Toastify;
  });

  test("formatDate and related helpers handle null/valid dates", () => {
    expect(window.formatDate(null)).toBe("Sin fecha");
    const iso = "2023-08-10T15:30:00Z";
    expect(typeof window.formatDate(iso)).toBe("string");
    expect(window.formatShortDate(iso)).toMatch(/\d{2}\/\d{2}\/\d{4}/);
    expect(window.formatOnlyDate(iso)).toMatch(/2023/);
    expect(window.formatDateTime(iso)).toMatch(/2023/);
    expect(window.formatDateTimeForInput(iso)).toMatch(
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/
    );
  });

  test("getAuthHeaders includes token when present", () => {
    window.localStorage.setItem("authToken", "MY.TOKEN.VALUE");
    const headers = window.getAuthHeaders({ Accept: "application/json" });
    expect(headers.Authorization).toBe("Bearer MY.TOKEN.VALUE");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers.Accept).toBe("application/json");
  });

  test("isAuthenticated handles invalid token gracefully", () => {
    // store an invalid token that will break JSON parse
    window.localStorage.setItem("authToken", "not.a.jwt");
    expect(window.isAuthenticated()).toBe(false);
    // token should be removed on invalid parse
    expect(window.localStorage.getItem("authToken")).toBe(null);
  });

  test("fetch interceptor adds Authorization header when token exists", async () => {
    // Reset modules, set a mock fetch BEFORE requiring the module so the interceptor
    // captures this mock as the original _fetch.
    jest.resetModules();
    const calls = [];
    const mockOriginalFetch = jest.fn((input, init) => {
      calls.push({ input, init });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    global.fetch = mockOriginalFetch;
    // re-require the module so the IIFE captures mockOriginalFetch as _fetch
    require("../app");

    window.localStorage.setItem("authToken", "TOKEN123");
    await window.fetch("/api/foo", { method: "GET" });

    expect(calls.length).toBeGreaterThan(0);
    // aceptar diferentes formas en que el mock/interceptor puede exponer headers
    const authHeader =
      calls[0].init?.headers?.Authorization ||
      calls[0].init?.Authorization ||
      calls[0].Authorization;
    expect(authHeader).toBe("Bearer TOKEN123");

    // cleanup: reset modules and delete our global.fetch mock
    jest.resetModules();
    delete global.fetch;
    require("../app");
  });

  test("showToast fallback uses alert when Toastify missing", () => {
    const alerts = [];
    global.alert = jest.fn((m) => alerts.push(m));
    window.showToast("Hola mundo", "info");
    expect(alerts.length).toBe(1);
    expect(alerts[0]).toBe("Hola mundo");
  });

  test("getAuthToken and getUserType behavior", () => {
    window.localStorage.setItem("authToken", "ABC");
    window.localStorage.setItem("userType", "admin");
    expect(window.getAuthToken()).toBe("ABC");
    expect(window.getUserType()).toBe("admin");

    // default when no userType
    window.localStorage.removeItem("userType");
    expect(window.getUserType()).toBe("student");
  });

  test("isAuthenticated accepts valid token and rejects expired token", () => {
    // valid token with future exp
    const payloadFuture = { exp: Math.floor(Date.now() / 1000) + 3600 };
    const b64Future = btoa(JSON.stringify(payloadFuture));
    window.localStorage.setItem("authToken", `a.${b64Future}.c`);
    expect(window.isAuthenticated()).toBe(true);
    // token should still be present
    expect(window.localStorage.getItem("authToken")).not.toBeNull();

    // expired token
    const payloadPast = { exp: Math.floor(Date.now() / 1000) - 10 };
    const b64Past = btoa(JSON.stringify(payloadPast));
    window.localStorage.setItem("authToken", `a.${b64Past}.c`);
    expect(window.isAuthenticated()).toBe(false);
    // token removed after expiry
    expect(window.localStorage.getItem("authToken")).toBeNull();
  });

  test("checkAuthAndRedirect redirects when not authenticated and returns true when ok", () => {
    // not authenticated case
    window.localStorage.removeItem("authToken");
    const fakeLocation = { href: "/orig", pathname: "/dashboard/" };
    Object.defineProperty(window, "location", {
      value: fakeLocation,
      writable: true,
    });

    expect(window.checkAuthAndRedirect()).toBe(false);
    expect(window.location.href).toBe("/");

    // authenticated case
    const payloadFuture = { exp: Math.floor(Date.now() / 1000) + 3600 };
    const b64Future = btoa(JSON.stringify(payloadFuture));
    window.localStorage.setItem("authToken", `a.${b64Future}.c`);

    // reset href to origin
    window.location.href = "/orig";
    expect(window.checkAuthAndRedirect()).toBe(true);
    expect(window.location.href).toBe("/orig");
  });

  test("fetch interceptor adds Content-Type when body present and headers provided", async () => {
    jest.resetModules();
    const calls = [];
    const mockOriginalFetch = jest.fn((input, init) => {
      calls.push({ input, init });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    global.fetch = mockOriginalFetch;
    require("../app");

    // call fetch with body and empty headers object so code adds Content-Type
    await window.fetch("/api/x", {
      method: "POST",
      body: JSON.stringify({ a: 1 }),
      headers: {},
    });

    expect(calls.length).toBeGreaterThan(0);
    const contentType =
      calls[0].init?.headers?.["Content-Type"] ||
      calls[0].init?.["Content-Type"];
    expect(contentType).toBe("application/json");

    // cleanup
    jest.resetModules();
    delete global.fetch;
    require("../app");
  });

  test("showToast uses Toastify when available", () => {
    const showMock = jest.fn();
    global.Toastify = jest.fn(() => ({ showToast: showMock }));

    window.showToast("Mensaje test", "success");

    expect(global.Toastify).toHaveBeenCalled();
    expect(showMock).toHaveBeenCalled();

    // cleanup
    delete global.Toastify;
  });
});
