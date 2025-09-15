const registrationsManager = require("../registrations.js");

describe("registrationsManager additional flows and error handling", () => {
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

  test("updateRegistration sends PUT and closes modal on success", async () => {
    const comp = registrationsManager();
    global.localStorage.setItem("authToken", "tk");
    comp.editMode = true;
    comp.currentRegistration = {
      id: 21,
      student_id: "5",
      activity_id: "8",
      status: "Confirmado",
    };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 21 }),
    });
    await comp.updateRegistration();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/registrations/21",
      expect.objectContaining({ method: "PUT" })
    );
    expect(comp.showModal).toBe(false);
  });

  test("changeRegistrationStatus updates and handles failure", async () => {
    const comp = registrationsManager();
    global.localStorage.setItem("authToken", "tk");
    comp.registrations = [
      { id: 30, student_id: 6, activity_id: 9, status: "Registrado" },
    ];
    // first, success
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await comp.changeRegistrationStatus(30, "Confirmado");
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/registrations/30",
      expect.objectContaining({ method: "PUT" })
    );

    // now simulate failure
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ message: "err" }),
    });
    await comp.changeRegistrationStatus(30, "Asistió");
    expect(global.showToast).toHaveBeenCalledWith(
      "Error al cambiar estado del registro",
      "error"
    );
  });

  test("deleteRegistration handles no selection gracefully and handles success delete", async () => {
    const comp = registrationsManager();
    // no registrationToDelete -> should simply return
    comp.registrationToDelete = null;
    await comp.deleteRegistration();

    // now set and delete
    global.localStorage.setItem("authToken", "tk");
    comp.registrationToDelete = { id: 42 };
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await comp.deleteRegistration();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/registrations/42",
      expect.objectContaining({ method: "DELETE" })
    );
  });

  test("loadRegistrations handles network timeout (fetch rejects)", async () => {
    const comp = registrationsManager();
    global.localStorage.setItem("authToken", "tk");
    global.fetch.mockRejectedValueOnce(new Error("timeout"));
    await comp.loadRegistrations();
    expect(global.showToast).toHaveBeenCalledWith(expect.any(String), "error");
  });
});
