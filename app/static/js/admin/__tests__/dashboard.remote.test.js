const adminDashboard = require("../dashboard.js");

describe("adminDashboard remote/loaders", () => {
  let mgr;
  beforeEach(() => {
    // ensure window exists
    if (typeof window === "undefined") global.window = {};
    // ensure we have a usable localStorage (jsdom provides one); if not, provide a minimal polyfill
    if (
      !window.localStorage ||
      typeof window.localStorage.setItem !== "function"
    ) {
      window.localStorage = (function () {
        let store = {};
        return {
          getItem: (k) => (k in store ? store[k] : null),
          setItem: (k, v) => (store[k] = v),
          removeItem: (k) => delete store[k],
        };
      })();
    }
    // set a fake token so loaders run
    window.localStorage.setItem("authToken", "FAKE_TOKEN");
    // mirror on global in case code references global.localStorage
    global.localStorage = window.localStorage;
    // clear any global.fetch set by other tests
    if (global.fetch) delete global.fetch;
    mgr = adminDashboard();
    // ensure showToast exists
    global.showToast = jest.fn();
  });

  afterEach(() => {
    // clean up fetch mock between tests
    if (global.fetch && global.fetch.mock) global.fetch.mockRestore?.();
    delete global.fetch;
  });

  test("loadStats updates this.stats based on API response", async () => {
    const statsResponse = {
      total_students: 10,
      active_events: 2,
      total_activities: 5,
      today_attendances: 3,
    };
    global.fetch = jest.fn((url) => {
      if (url === "/api/stats/")
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(statsResponse),
        });
      return Promise.resolve({ ok: false });
    });

    await mgr.loadStats();

    const studentsStat = mgr.stats.find((s) => s.id === "students");
    const eventsStat = mgr.stats.find((s) => s.id === "events");
    const activitiesStat = mgr.stats.find((s) => s.id === "activities");
    const attendancesStat = mgr.stats.find((s) => s.id === "attendances");

    expect(studentsStat.value).toBe(String(statsResponse.total_students));
    expect(eventsStat.value).toBe(String(statsResponse.active_events));
    expect(activitiesStat.value).toBe(String(statsResponse.total_activities));
    expect(attendancesStat.value).toBe(String(statsResponse.today_attendances));
  });

  test("loadUpcomingEvents filters events within next 30 days", async () => {
    const now = new Date();
    const in15 = new Date(now);
    in15.setDate(now.getDate() + 15);
    const in40 = new Date(now);
    in40.setDate(now.getDate() + 40);

    const events = [
      { id: 1, start_date: in15.toISOString() },
      { id: 2, start_date: in40.toISOString() },
      { id: 3, start_date: now.toISOString() },
    ];

    global.fetch = jest.fn((url) => {
      if (url.startsWith("/api/events?"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ events }),
        });
      return Promise.resolve({ ok: false });
    });

    await mgr.loadUpcomingEvents();
    expect(mgr.upcomingEvents.length).toBeGreaterThanOrEqual(1);
    // should include id 1 and 3 but not 2
    expect(mgr.upcomingEvents.some((e) => e.id === 1)).toBe(true);
    expect(mgr.upcomingEvents.some((e) => e.id === 2)).toBe(false);
  });

  test("loadRecentActivities filters last 7 days", async () => {
    const now = new Date();
    const in3 = new Date(now);
    in3.setDate(now.getDate() - 3);
    const in10 = new Date(now);
    in10.setDate(now.getDate() - 10);

    const activities = [
      { id: "a1", created_at: in3.toISOString() },
      { id: "a2", created_at: in10.toISOString() },
    ];

    global.fetch = jest.fn((url) => {
      if (url.startsWith("/api/activities?"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ activities }),
        });
      return Promise.resolve({ ok: false });
    });

    await mgr.loadRecentActivities();
    expect(mgr.recentActivities.some((a) => a.id === "a1")).toBe(true);
    expect(mgr.recentActivities.some((a) => a.id === "a2")).toBe(false);
  });

  test("loadDashboardData sets isLoading while running and false after", async () => {
    // stub the underlying loaders to control timing
    mgr.loadEvents = jest.fn(() => Promise.resolve());
    mgr.loadActivities = jest.fn(() => Promise.resolve());
    mgr.loadStats = jest.fn(() => Promise.resolve());
    mgr.loadUpcomingEvents = jest.fn(() => Promise.resolve());
    mgr.loadRecentActivities = jest.fn(() => Promise.resolve());

    const p = mgr.loadDashboardData();
    expect(mgr.isLoading).toBe(true);
    await p;
    expect(mgr.isLoading).toBe(false);
  });
});
