const registrationsManager = require("../registrations.js");

describe("registrationsManager fetch interactions", () => {
  let origFetch;
  let origLs;
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

  test("loadRegistrations fetches and sets registrations", async () => {
    const comp = registrationsManager();
    global.localStorage.setItem("authToken", "tk");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        registrations: [{ id: 1, status: "Registrado" }],
        page: 1,
        pages: 1,
        total: 1,
      }),
    });
    await comp.loadRegistrations();
    expect(global.fetch).toHaveBeenCalled();
    expect(comp.registrations.length).toBe(1);
    expect(comp.totalItems).toBe(1);
  });

  test("createRegistration posts and closes modal on success", async () => {
    const comp = registrationsManager();
    global.localStorage.setItem("authToken", "tk");
    comp.currentRegistration = { student_id: "3", activity_id: "7" };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 44 }),
    });
    await comp.createRegistration();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/registrations",
      expect.objectContaining({ method: "POST" })
    );
    expect(comp.showModal).toBe(false);
  });

  test("getAvailableStatusTransitions returns correct transitions", () => {
    const comp = registrationsManager();
    expect(comp.getAvailableStatusTransitions("Registrado")).toEqual(
      expect.arrayContaining(["Confirmado", "Cancelado"])
    );
    expect(comp.getAvailableStatusTransitions("Asistió")).toEqual([
      "Confirmado",
    ]);
  });
});
