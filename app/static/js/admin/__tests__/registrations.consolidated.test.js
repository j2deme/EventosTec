require("../../app.js");
const registrationsManager = require("../registrations.js");

describe("registrationsManager (consolidated)", () => {
  describe("unit helpers and pagination", () => {
    let mgr;
    beforeEach(() => {
      mgr = registrationsManager();
    });

    test("getVisiblePages returns sensible window", () => {
      mgr.currentPage = 5;
      mgr.totalPages = 10;
      const pages = mgr.getVisiblePages();
      expect(pages.length).toBeGreaterThan(0);
      expect(pages).toContain(5);
    });

    test("previousPage and nextPage call loadRegistrations appropriately", () => {
      const spy = jest.spyOn(mgr, "loadRegistrations");
      mgr.currentPage = 2;
      mgr.totalPages = 3;
      mgr.previousPage();
      expect(spy).toHaveBeenCalledWith(1);
      mgr.nextPage();
      expect(spy).toHaveBeenCalledWith(2);
      spy.mockRestore();
    });
  });

  describe("http, fetch and error branches", () => {
    let origFetch, origLs, origToast;
    beforeAll(() => {
      origFetch = global.fetch;
      origLs = global.localStorage;
      origToast = global.showToast;
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
      global.fetch = origFetch;
      global.localStorage = origLs;
      global.showToast = origToast;
    });

    test("loadRegistrations throws/sets error when token missing", async () => {
      const comp = registrationsManager();
      global.localStorage.removeItem &&
        global.localStorage.removeItem("authToken");
      global.fetch = jest.fn(() => Promise.resolve({ ok: false }));
      await comp.loadRegistrations();
      expect(comp.errorMessage).toBeTruthy();
    });

    test("loadRegistrations handles non-ok response and sets errorMessage", async () => {
      const comp = registrationsManager();
      global.localStorage.setItem("authToken", "tok");
      global.fetch = jest.fn(() =>
        Promise.resolve({ ok: false, status: 500, statusText: "err" }),
      );
      await comp.loadRegistrations();
      expect(comp.errorMessage).toMatch(/Error al cargar registros/);
      expect(global.showToast).toHaveBeenCalledWith(
        "Error al cargar registros",
        "error",
      );
    });
  });

  describe("fetch interactions and flows", () => {
    let origFetch, origLs;
    beforeEach(() => {
      origFetch = global.fetch;
      global.fetch = jest.fn();
      origLs = global.localStorage;
      global.localStorage = {
        _store: {},
        getItem(k) {
          return this._store[k] || null;
        },
        setItem(k, v) {
          this._store[k] = String(v);
        },
      };
      global.showToast = jest.fn();
    });
    afterEach(() => {
      global.fetch = origFetch;
      global.localStorage = origLs;
      delete global.showToast;
      jest.restoreAllMocks();
    });

    test("loadRegistrations populates registrations and updates pagination", async () => {
      const comp = registrationsManager();
      global.localStorage.setItem("authToken", "t");
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          registrations: [{ id: 1 }],
          page: 1,
          pages: 1,
          total: 1,
        }),
      });
      await comp.loadRegistrations(1);
      // accept parameter order variations (page/per_page)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringMatching(
          /\/api\/registrations.*(?:per_page=10.*page=1|page=1.*per_page=10)/,
        ),
        expect.any(Object),
      );
      expect(comp.registrations.length).toBe(1);
    });

    test("createRegistration posts and refreshes list on success", async () => {
      const comp = registrationsManager();
      global.localStorage.setItem("authToken", "tok");
      comp.currentRegistration = { student_id: "1", activity_id: "2" };
      // First call: POST create -> succeed
      global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
      // Second call: loadRegistrations triggered after creation -> return empty list
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registrations: [], page: 1, pages: 1, total: 0 }),
      });
      await comp.createRegistration();
      // After successful creation it calls loadRegistrations; ensure no error
      expect(comp.errorMessage).toBe("");
    });
  });
});
