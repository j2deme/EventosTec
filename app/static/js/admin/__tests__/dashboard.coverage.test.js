const adminDashboard = require("../dashboard");

describe("adminDashboard extra coverage", () => {
  let mgr;
  const originalLocation = global.window.location;

  beforeEach(() => {
    // Ensure a clean storage state and token when needed
    window.localStorage.clear();
    mgr = adminDashboard();
  });

  afterEach(() => {
    // Restore location if replaced
    try {
      Object.defineProperty(window, "location", {
        value: originalLocation,
        writable: true,
      });
    } catch (e) {
      // ignore restore errors
    }
    jest.resetAllMocks();
  });

  test("getTabFromUrl and isValidTab", () => {
    window.location.hash = "#events";
    expect(mgr.getTabFromUrl()).toBe("events");
    expect(mgr.isValidTab("events")).toBe(true);
    expect(mgr.isValidTab("nope")).toBe(false);
  });

  test("setInitialTab picks hash first then saved tab", () => {
    // hash should have precedence
    window.location.hash = "#activities";
    window.localStorage.setItem("adminActiveTab", "events");
    mgr.setInitialTab();
    expect(mgr.activeTab).toBe("activities");

    // If no hash, saved tab should be used and hash updated
    window.location.hash = "";
    window.localStorage.setItem("adminActiveTab", "registrations");
    mgr.setInitialTab();
    expect(mgr.activeTab).toBe("registrations");
    // hash should reflect saved tab (when not overview)
    expect(
      window.location.hash.endsWith("#registrations") ||
        window.location.hash === "#registrations"
    ).toBe(true);
  });

  test("setActiveTab updates storage and hash for non-overview", () => {
    mgr.setActiveTab("attendances");
    expect(window.localStorage.getItem("adminActiveTab")).toBe("attendances");
    expect(
      window.location.hash.endsWith("#attendances") ||
        window.location.hash === "#attendances"
    ).toBe(true);
  });

  test("setActiveTab for overview tries to clear hash without throwing", () => {
    // set some initial hash
    window.location.hash = "#events";
    // should not throw even if history API used internally
    expect(() => mgr.setActiveTab("overview")).not.toThrow();
    expect(window.localStorage.getItem("adminActiveTab")).toBe("overview");
  });

  test("loadStats maps API response to stats entries", async () => {
    window.localStorage.setItem("authToken", "FAKE");
    const fakeStats = {
      total_students: 10,
      active_events: 2,
      total_activities: 5,
      today_attendances: 3,
    };
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(fakeStats) })
    );

    await mgr.loadStats();

    const students = mgr.stats.find((s) => s.id === "students");
    const events = mgr.stats.find((s) => s.id === "events");
    const activities = mgr.stats.find((s) => s.id === "activities");
    const attendances = mgr.stats.find((s) => s.id === "attendances");

    expect(students.value).toBe("10");
    expect(events.value).toBe("2");
    expect(activities.value).toBe("5");
    expect(attendances.value).toBe("3");
  });

  test("loadUpcomingEvents filters events within 30 days", async () => {
    window.localStorage.setItem("authToken", "FAKE");
    const now = new Date();
    const in5 = new Date(now);
    in5.setDate(now.getDate() + 5);
    const in40 = new Date(now);
    in40.setDate(now.getDate() + 40);

    const events = [
      { id: 1, start_date: in5.toISOString() },
      { id: 2, start_date: in40.toISOString() },
    ];

    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(events) })
    );

    await mgr.loadUpcomingEvents();

    expect(mgr.upcomingEvents.length).toBe(1);
    expect(mgr.upcomingEvents[0].id).toBe(1);
  });

  test("loadRecentActivities filters activities within last 7 days", async () => {
    window.localStorage.setItem("authToken", "FAKE");
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    const old = new Date(now);
    old.setDate(now.getDate() - 10);

    const activities = [
      { id: "a", created_at: yesterday.toISOString() },
      { id: "b", created_at: old.toISOString() },
    ];

    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(activities) })
    );

    await mgr.loadRecentActivities();

    expect(mgr.recentActivities.length).toBe(1);
    expect(mgr.recentActivities[0].id).toBe("a");
  });

  test("logout cancels when confirm false and removes items when confirm true", () => {
    window.localStorage.setItem("authToken", "FAKE");
    window.localStorage.setItem("userType", "admin");

    // case cancelled
    global.confirm = jest.fn(() => false);
    mgr.logout();
    expect(window.localStorage.getItem("authToken")).toBe("FAKE");

    // case confirmed: override location to avoid jsdom navigation
    global.confirm = jest.fn(() => true);
    const fakeLocation = { href: "http://example.test/orig" };
    Object.defineProperty(window, "location", {
      value: fakeLocation,
      writable: true,
    });

    mgr.logout();
    expect(window.localStorage.getItem("authToken")).toBe(null);
    expect(window.localStorage.getItem("userType")).toBe(null);
    expect(window.location.href).toBe("/");
  });

  test("loadDashboardData sets errorMessage when a loader throws", async () => {
    window.localStorage.setItem("authToken", "FAKE");
    // Force one loader to reject
    mgr.loadEvents = jest.fn(() => Promise.reject(new Error("boom")));

    await mgr.loadDashboardData();

    expect(mgr.errorMessage).toBe("Error al cargar datos del dashboard");
    expect(mgr.isLoading).toBe(false);
  });

  test("loadActivities calls showToast on fetch error", async () => {
    window.localStorage.setItem("authToken", "FAKE");
    global.fetch = jest.fn(() => Promise.reject(new Error("net")));
    global.showToast = jest.fn();

    await mgr.loadActivities();

    expect(global.showToast).toHaveBeenCalledWith(
      "Error al cargar actividades",
      "error"
    );
  });

  test("loadEvents does not call fetch when token missing", async () => {
    window.localStorage.removeItem("authToken");
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
    );

    await mgr.loadEvents();

    expect(global.fetch).not.toHaveBeenCalled();
  });

  test("updateLocationAndStorage swallows exceptions when hash setter throws", () => {
    // Create a location object whose hash setter throws
    const fakeLocation = {
      get hash() {
        return "#orig";
      },
      set hash(v) {
        throw new Error("boom");
      },
      pathname: "/orig",
    };

    Object.defineProperty(window, "location", {
      value: fakeLocation,
      writable: true,
    });

    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

    // Should not throw
    expect(() => mgr.updateLocationAndStorage("events")).not.toThrow();
    expect(window.localStorage.getItem("adminActiveTab")).toBe("events");
    expect(warnSpy).toHaveBeenCalled();

    warnSpy.mockRestore();
  });

  test("formatTime, formatDate fallback and toggleSidebar", () => {
    // formatTime with falsy input
    expect(mgr.formatTime(null)).toBe("--:--");

    // formatDate fallback when window.formatDate not present
    delete window.formatDate;
    expect(mgr.formatDate(null)).toBe("Sin fecha");

    // formatDate uses global formatDate when present
    window.formatDate = jest.fn(() => "FORMATED");
    expect(mgr.formatDate("2020-01-01")).toBe("FORMATED");

    // toggleSidebar
    mgr.sidebarOpen = false;
    mgr.toggleSidebar();
    expect(mgr.sidebarOpen).toBe(true);
  });

  test("setupEventListeners triggers handleLocationChange on popstate/hashchange", () => {
    const spy = jest.spyOn(mgr, "handleLocationChange");
    mgr.setupEventListeners();

    window.dispatchEvent(new PopStateEvent("popstate"));
    window.dispatchEvent(new HashChangeEvent("hashchange"));

    expect(spy).toHaveBeenCalledTimes(2);
    spy.mockRestore();
  });

  test("setupDataUpdateListeners wires events to loaders", () => {
    mgr.loadEvents = jest.fn();
    mgr.loadActivities = jest.fn();

    mgr.setupDataUpdateListeners();

    window.dispatchEvent(new CustomEvent("event-created"));
    window.dispatchEvent(new CustomEvent("event-updated"));
    window.dispatchEvent(new CustomEvent("event-deleted"));
    window.dispatchEvent(new CustomEvent("activity-created"));
    window.dispatchEvent(new CustomEvent("activity-updated"));
    window.dispatchEvent(new CustomEvent("activity-deleted"));

    expect(mgr.loadEvents).toHaveBeenCalledTimes(3);
    expect(mgr.loadActivities).toHaveBeenCalledTimes(3);
  });

  test("setInitialTab clears hash when savedTab is overview", () => {
    // Use an invalid hash so getTabFromUrl() returns null and savedTab branch runs
    window.location.hash = "#invalid";
    window.localStorage.setItem("adminActiveTab", "overview");

    const replaceSpy = jest
      .spyOn(history, "replaceState")
      .mockImplementation(() => {});

    mgr.setInitialTab();

    expect(mgr.activeTab).toBe("overview");
    expect(replaceSpy).toHaveBeenCalled();

    replaceSpy.mockRestore();
  });

  test("setActiveTab with invalid id warns and leaves tab unchanged", () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const before = mgr.activeTab;

    mgr.setActiveTab("nope");

    expect(warnSpy).toHaveBeenCalled();
    expect(mgr.activeTab).toBe(before);

    warnSpy.mockRestore();
  });

  test("getTabFromUrl returns null for invalid hash", () => {
    window.location.hash = "#nope";
    expect(mgr.getTabFromUrl()).toBeNull();
  });

  test("updateStats delegates to loadStats", () => {
    mgr.loadStats = jest.fn();
    mgr.updateStats();
    expect(mgr.loadStats).toHaveBeenCalled();
  });

  test("handleLocationChange falls back to overview when savedTab invalid", () => {
    window.location.hash = "";
    window.localStorage.setItem("adminActiveTab", "invalid_tab");

    mgr.handleLocationChange();

    expect(mgr.activeTab).toBe("overview");
  });

  test("loadDashboardData success path populates values when fetch returns ok", async () => {
    window.localStorage.setItem("authToken", "FAKE");

    // Mock fetch to return different payloads based on URL
    global.fetch = jest.fn((url) => {
      if (url.startsWith("/api/events/") || url.startsWith("/api/events?")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve([{ id: 1, start_date: new Date().toISOString() }]),
        });
      }
      if (
        url.startsWith("/api/activities/") ||
        url.startsWith("/api/activities?")
      ) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve([
              { id: "a", created_at: new Date().toISOString() },
            ]),
        });
      }
      if (url.startsWith("/api/stats/")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              total_students: 1,
              active_events: 1,
              total_activities: 1,
              today_attendances: 0,
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });

    await mgr.loadDashboardData();

    expect(mgr.isLoading).toBe(false);
    // events/activities/stats arrays should have been populated or updated
    expect(Array.isArray(mgr.events)).toBe(true);
    expect(Array.isArray(mgr.activities)).toBe(true);
    // stats should include students set to '1'
    const students = mgr.stats.find((s) => s.id === "students");
    expect(students.value).toBe("1");
  });
});
