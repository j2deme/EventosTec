/** Consolidated dashboard tests (merged from multiple dashboard.*.test.js files) */

/** @jest-environment jsdom */
jest.resetModules();

const adminDashboard = require("../dashboard");

describe("adminDashboard consolidated tests", () => {
  describe("unit behaviors", () => {
    let mgr;
    beforeEach(() => {
      global.localStorage = {
        getItem: jest.fn(),
        setItem: jest.fn(),
        removeItem: jest.fn(),
      };
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
      mgr.setActiveTab("events");
      expect(window.location.hash).toBe("#events");
    });

    test("toggleSidebar and formatTime/logout behavior", () => {
      mgr.toggleSidebar();
      expect(mgr.sidebarOpen).toBe(true);
      expect(mgr.formatTime(null)).toBe("--:--");

      global.confirm = jest.fn(() => false);
      // Prevent jsdom navigation by substituting a safe location object
      const origLocation = window.location;
      Object.defineProperty(window, "location", {
        value: {
          href: "http://example.test/orig",
          pathname: "/orig",
          hash: "",
        },
        writable: true,
      });
      mgr.logout();
      expect(window.location.href.endsWith("/")).toBe(false);

      global.confirm = jest.fn(() => true);
      mgr.logout();
      // After logout the module sets location.href = '/'
      expect(window.location.href).toBe("/");

      // restore original location
      Object.defineProperty(window, "location", {
        value: origLocation,
        writable: true,
      });
    });
  });

  describe("factory and remote loaders", () => {
    let origFetch, origLocalStorage, origShowToast, mgr;
    beforeEach(() => {
      origFetch = global.fetch;
      origLocalStorage = global.localStorage;
      origShowToast = global.showToast;
      global.localStorage = {
        store: {},
        getItem(key) {
          return this.store[key] || null;
        },
        setItem(key, val) {
          this.store[key] = String(val);
        },
        removeItem(key) {
          delete this.store[key];
        },
      };
      global.showToast = jest.fn();
      if (global.fetch) delete global.fetch;
      mgr = adminDashboard();
    });

    afterEach(() => {
      global.fetch = origFetch;
      global.localStorage = origLocalStorage;
      global.showToast = origShowToast;
      try {
        delete global.fetch;
      } catch (e) {}
    });

    test("init sets default active tab and can loadEvents without token", async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve([]) }),
      );
      const comp = adminDashboard();
      await comp.loadEvents();
      expect(comp.events).toEqual([]);
      comp.setActiveTab("events");
      expect(comp.activeTab).toBe("events");
    });

    test("loadStats updates stats from API", async () => {
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
      // loadStats requires an auth token
      global.localStorage.setItem("authToken", "tok");
      await mgr.loadStats();
      const students = mgr.stats.find((s) => s.id === "students");
      expect(students.value).toBe(String(statsResponse.total_students));
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
        if (url.startsWith("/api/events"))
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ events }),
          });
        return Promise.resolve({ ok: false });
      });
      // loader requires auth token
      global.localStorage.setItem("authToken", "tok");
      await mgr.loadUpcomingEvents();
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
        if (url.startsWith("/api/activities"))
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ activities }),
          });
        return Promise.resolve({ ok: false });
      });
      // loader requires auth token
      global.localStorage.setItem("authToken", "tok");
      await mgr.loadRecentActivities();
      expect(mgr.recentActivities.some((a) => a.id === "a1")).toBe(true);
      expect(mgr.recentActivities.some((a) => a.id === "a2")).toBe(false);
    });

    test("loadDashboardData sets isLoading while running and false after", async () => {
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

  describe("integration-like flows and edge cases", () => {
    let origLocalStorage, origShowToast, origFetch, mgr;
    beforeEach(() => {
      origLocalStorage = global.localStorage;
      origShowToast = global.showToast;
      origFetch = global.fetch;
      // Ensure window.location exists and is safe for tests
      this.__origLocation =
        typeof window !== "undefined" ? window.location : undefined;
      try {
        Object.defineProperty(window, "location", {
          value: { pathname: "/", hash: "", href: "/" },
          writable: true,
        });
      } catch (e) {}
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
      mgr = adminDashboard();
    });
    afterEach(() => {
      global.localStorage = origLocalStorage;
      global.showToast = origShowToast;
      global.fetch = origFetch;
    });

    test("loadDashboardData populates events, activities, stats, upcoming and recent", async () => {
      const comp = adminDashboard();
      global.localStorage.setItem("authToken", "tok");
      const now = new Date();
      const future = new Date(
        now.getTime() + 3 * 24 * 60 * 60 * 1000,
      ).toISOString();
      const past = new Date(
        now.getTime() - 2 * 24 * 60 * 60 * 1000,
      ).toISOString();
      global.fetch = jest.fn((url) => {
        if (url.startsWith("/api/events/"))
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve([
                { id: 1, start_date: future, end_date: future },
              ]),
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
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      });
      await comp.loadDashboardData();
      expect(comp.events.length).toBeGreaterThan(0);
      expect(Array.isArray(comp.recentActivities)).toBe(true);
      expect(comp.stats.find((s) => s.id === "students").value).toBe("10");
    });

    test("setInitialTab respects hash and saved tab", () => {
      // make test independent of previous tests: clear hash and saved tab BEFORE creating the component
      try {
        Object.defineProperty(window, "location", {
          value: { pathname: "/", hash: "", href: "/" },
          writable: true,
        });
      } catch (e) {}
      try {
        if (global.localStorage && global.localStorage.store)
          global.localStorage.store = {};
      } catch (e) {}
      try {
        global.localStorage.setItem("adminActiveTab", null);
      } catch (e) {}
      // ensure window.localStorage matches global/local mock
      try {
        window.localStorage = global.localStorage;
      } catch (e) {}
      const comp = adminDashboard();
      comp.setInitialTab();
      expect(comp.activeTab).toBe("overview");
      global.localStorage.setItem("adminActiveTab", "activities");
      comp.setInitialTab();
      expect(comp.activeTab).toBe("activities");
    });

    test("logout clears storage on confirm and does not when cancelled", () => {
      window.localStorage.setItem("authToken", "FAKE");
      window.localStorage.setItem("userType", "admin");
      global.confirm = jest.fn(() => false);
      mgr.logout();
      expect(window.localStorage.getItem("authToken")).toBe("FAKE");
      global.confirm = jest.fn(() => true);
      // Temporarily replace window.location with a safe object
      const origLoc = window.location;
      const fakeLocation = {
        href: "http://example.test/orig",
        pathname: "/orig",
        hash: "",
      };
      Object.defineProperty(window, "location", {
        value: fakeLocation,
        writable: true,
      });
      mgr.logout();
      expect(window.localStorage.getItem("authToken")).toBe(null);
      expect(window.location.href).toBe("/");
      // restore original location
      Object.defineProperty(window, "location", {
        value: origLoc,
        writable: true,
      });
    });

    test("loadDashboardData sets errorMessage when a loader throws", async () => {
      window.localStorage.setItem("authToken", "FAKE");
      mgr.loadEvents = jest.fn(() => Promise.reject(new Error("boom")));
      await mgr.loadDashboardData();
      expect(mgr.errorMessage).toBe("Error al cargar datos del dashboard");
      expect(mgr.isLoading).toBe(false);
    });

    test("updateLocationAndStorage swallows exceptions when hash setter throws", () => {
      // Replace location with a fake that throws on hash set, but restore afterwards
      const origLoc = window.location;
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
      expect(() => mgr.updateLocationAndStorage("events")).not.toThrow();
      expect(window.localStorage.getItem("adminActiveTab")).toBe("events");
      expect(warnSpy).toHaveBeenCalled();
      warnSpy.mockRestore();
      // restore location to avoid affecting later tests
      Object.defineProperty(window, "location", {
        value: origLoc,
        writable: true,
      });
    });

    test("formatTime, formatDate fallback and toggleSidebar", () => {
      expect(mgr.formatTime(null)).toBe("--:--");
      delete window.formatDate;
      expect(mgr.formatDate(null)).toBe("Sin fecha");
      window.formatDate = jest.fn(() => "FORMATED");
      expect(mgr.formatDate("2020-01-01")).toBe("FORMATED");
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
  });
});
