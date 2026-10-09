require("../../app.js");
const registrationsManager = require("../registrations.js");

describe("registrationsManager (consolidated)", () => {
  describe("unit helpers and pagination", () => {
    let mgr;
    beforeEach(() => {
      mgr = registrationsManager();
    });

    test("getVisiblePages delegates al helper compartido (alias)", () => {
      // La ventana ahora la calcula paginationHelpers.buildWindow; este
      // método queda como alias para no romper llamadas existentes.
      mgr.currentPage = 5;
      mgr.totalPages = 10;
      mgr.pagination = window.paginationHelpers.buildState(
        { current_page: 5, pages: 10, total: 100 },
        mgr.perPage,
      );

      const pages = mgr.getVisiblePages();

      expect(pages.length).toBeGreaterThan(0);
      expect(pages).toContain(5);
      // Nunca expone los puntos suspensivos como si fueran páginas.
      expect(pages.every((p) => Number.isInteger(p))).toBe(true);
    });

    test("la ventana de páginas queda acotada (regresión del bug original)", () => {
      // 5790 registros a 50 por página = 116 páginas. Antes de unificar,
      // registrations usaba su propia ventana ±2 y el resto de vistas
      // renderizaba TODAS las páginas.
      mgr.currentPage = 58;
      mgr.totalPages = 116;
      mgr.pagination = window.paginationHelpers.buildState(
        { current_page: 58, pages: 116, total: 5790 },
        mgr.perPage,
      );

      expect(mgr.pagination.window.length).toBeLessThanOrEqual(11);
      expect(mgr.pagination.showJump).toBe(true);
    });

    test("setPerPage vuelve a la primera página", async () => {
      const spy = jest.spyOn(mgr, "loadRegistrations").mockResolvedValue();
      mgr.currentPage = 7;
      mgr.perPage = 50;

      mgr.setPerPage("100");

      expect(mgr.perPage).toBe(100);
      expect(mgr.currentPage).toBe(1);
      expect(spy).toHaveBeenCalledWith(1);
      spy.mockRestore();
    });

    test("changePage normaliza strings y respeta los límites", async () => {
      const spy = jest.spyOn(mgr, "loadRegistrations").mockResolvedValue();
      mgr.currentPage = 1;
      mgr.totalPages = 5;

      mgr.changePage("3");
      expect(spy).toHaveBeenCalledWith(3);
      expect(mgr.currentPage).toBe(3);

      spy.mockClear();
      mgr.changePage("abc");
      mgr.changePage(0);
      mgr.changePage(99);
      expect(spy).not.toHaveBeenCalled();
      spy.mockRestore();
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
      // accept parameter order variations (page/per_page). per_page=50 porque
      // esta vista maneja el mayor volumen (5790 registros en producción).
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringMatching(
          /\/api\/registrations.*(?:per_page=50.*page=1|page=1.*per_page=50)/,
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
