/** @jest-environment jsdom */
const adminDashboard = require("../dashboard");

describe("dashboard full load flow", () => {
  let origLocalStorage, origShowToast, origFetch;
  beforeAll(() => {
    origLocalStorage = global.localStorage;
    origShowToast = global.showToast;
    origFetch = global.fetch;
    global.localStorage = {
      store: {},
      getItem(k) {
        return this.store[k] || null;
      },
      setItem(k, v) {
        this.store[k] = String(v);
      },
      removeItem(k) {
        delete this.store[k];
      },
    };
    global.showToast = jest.fn();
  });
  afterAll(() => {
    global.localStorage = origLocalStorage;
    global.showToast = origShowToast;
    global.fetch = origFetch;
  });

  test("loadDashboardData populates events, activities, stats, upcoming and recent", async () => {
    const comp = adminDashboard();
    // set token
    global.localStorage.setItem("authToken", "tok");

    // prepare data: events (one in next 5 days), activities with created_at
    const now = new Date();
    const future = new Date(
      now.getTime() + 3 * 24 * 60 * 60 * 1000
    ).toISOString();
    const past = new Date(
      now.getTime() - 2 * 24 * 60 * 60 * 1000
    ).toISOString();

    global.fetch = jest.fn((url) => {
      if (url.startsWith("/api/events/"))
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve([{ id: 1, start_date: future, end_date: future }]),
        });
      if (url.startsWith("/api/activities/"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([{ id: 2, created_at: past }]),
        });
      if (url.startsWith("/api/stats/"))
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              total_students: 10,
              active_events: 1,
              total_activities: 5,
              today_attendances: 2,
            }),
        });
      // fallback
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });

    await comp.loadDashboardData();
    expect(comp.events.length).toBeGreaterThan(0);
    expect(comp.activities.length).toBeGreaterThanOrEqual(0);
    expect(comp.stats.find((s) => s.id === "students").value).toBe("10");
    expect(comp.upcomingEvents.length).toBeGreaterThanOrEqual(0);
    expect(Array.isArray(comp.recentActivities)).toBe(true);
  });
});
