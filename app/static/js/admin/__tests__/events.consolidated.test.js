require("../../app.js");
const eventsManager = require("../events.js");

describe("eventsManager (consolidated)", () => {
  describe("unit and helper methods", () => {
    let mgr;
    beforeEach(() => {
      global.showToast = jest.fn();
      mgr = eventsManager();
    });

    test("openCreateModal initializes currentEvent and showModal", () => {
      mgr.openCreateModal();
      expect(mgr.showModal).toBe(true);
      expect(mgr.currentEvent.name).toBe("");
    });

    test("openEditModal copies event and sets editingEvent", () => {
      const ev = { id: 5, name: "X", start_date: "2025-09-01T00:00" };
      mgr.openEditModal(ev);
      expect(mgr.showModal).toBe(true);
      expect(mgr.currentEvent.id).toBe(5);
    });

    test("changePage calls loadEvents only for valid page", () => {
      const spy = jest.spyOn(mgr, "loadEvents");
      mgr.pagination.last_page = 3;
      mgr.changePage(2);
      expect(spy).toHaveBeenCalledWith(2);
      spy.mockRestore();
    });
  });

  describe("http and fetch branches", () => {
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

    test("loadEvents throws/sets error when token missing", async () => {
      const comp = eventsManager();
      global.localStorage.removeItem &&
        global.localStorage.removeItem("authToken");
      global.fetch = jest.fn(() => Promise.resolve({ ok: false }));
      await comp.loadEvents();
      expect(comp.errorMessage).toBeTruthy();
    });

    test("loadEvents handles non-ok response and shows toast", async () => {
      const comp = eventsManager();
      global.localStorage.setItem("authToken", "tok");
      global.fetch = jest.fn(() =>
        Promise.resolve({ ok: false, status: 500, statusText: "err" }),
      );
      await comp.loadEvents();
      expect(comp.errorMessage).toMatch(/Error al cargar eventos/);
      expect(global.showToast).toHaveBeenCalledWith(
        "Error al cargar eventos",
        "error",
      );
    });

    test("createEvent handles non-ok and sets error", async () => {
      const comp = eventsManager();
      global.localStorage.setItem("authToken", "tok");
      comp.currentEvent = { name: "X" };
      global.fetch = jest.fn(() =>
        Promise.resolve({ ok: false, json: async () => ({ message: "bad" }) }),
      );
      await comp.createEvent();
      expect(comp.errorMessage).toBeTruthy();
    });
  });

  describe("fetch interactions and CRUD flows", () => {
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

    test("loadEvents fetches and sets events and pagination", async () => {
      const comp = eventsManager();
      global.localStorage.setItem("authToken", "t");
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          events: [
            {
              id: 1,
              name: "E",
              start_date: "2025-09-01T00:00",
              end_date: "2025-09-02T00:00",
            },
          ],
          current_page: 1,
          pages: 1,
          total: 1,
        }),
      });
      await comp.loadEvents(1);
      // accept parameter order variations (page/per_page) and optional sort
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringMatching(
          /\/api\/events.*(?:per_page=10.*page=1|page=1.*per_page=10)/,
        ),
        expect.any(Object),
      );
      expect(comp.events.length).toBeGreaterThan(0);
    });

    test("deleteEvent sends DELETE and dispatches event-deleted", async () => {
      const comp = eventsManager();
      global.localStorage.setItem("authToken", "tok");
      comp.eventToDelete = { id: 99 };
      global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
      const spy = jest.spyOn(global.window, "dispatchEvent");
      await comp.deleteEvent();
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/events/99",
        expect.objectContaining({ method: "DELETE" }),
      );
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({ type: "event-deleted" }),
      );
      spy.mockRestore();
    });
  });
});
