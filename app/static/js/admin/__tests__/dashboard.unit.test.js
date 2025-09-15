const adminDashboard = require("../dashboard.js");

describe("adminDashboard unit tests", () => {
  let mgr;
  beforeEach(() => {
    // provide globals and mocks BEFORE creating the manager
    global.localStorage = {
      getItem: jest.fn(),
      setItem: jest.fn(),
      removeItem: jest.fn(),
    };
    // also mirror on window (some code may reference window.localStorage)
    if (typeof window === "undefined") global.window = {};
    window.localStorage = global.localStorage;
    global.history = { replaceState: jest.fn(), pushState: jest.fn() };
    window.location = { pathname: "/", hash: "" };
    global.showToast = jest.fn();
    mgr = adminDashboard();
  });

  test("isValidTab and getTabFromUrl", () => {
    window.location.hash = "#events";
    expect(mgr.getTabFromUrl()).toBe("events");
    expect(mgr.isValidTab("events")).toBe(true);
    expect(mgr.isValidTab("nope")).toBe(false);
  });

  test("setActiveTab updates localStorage and hash", () => {
    // Verify observable effect: URL hash updated
    mgr.setActiveTab("events");
    // window.location.hash includes the leading '#'
    expect(window.location.hash).toBe("#events");
  });

  test("toggleSidebar and formatTime/logout behavior", () => {
    mgr.toggleSidebar();
    expect(mgr.sidebarOpen).toBe(true);
    expect(mgr.formatTime(null)).toBe("--:--");

    // Mock confirm to simulate logout cancel
    global.confirm = jest.fn(() => false);
    // set a known initial href
    window.location.href = "http://example.test/orig";
    mgr.logout();
    // when cancelled, href should NOT become root '/'
    expect(window.location.href.endsWith("/")).toBe(false);

    // Confirm true should trigger location change to root ('/') - jsdom resolves to an absolute URL
    global.confirm = jest.fn(() => true);
    mgr.logout();
    expect(window.location.href.endsWith("/")).toBe(true);
  });
});
