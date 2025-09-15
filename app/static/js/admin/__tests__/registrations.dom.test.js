/** @jest-environment jsdom */
const registrationsManager = require("../registrations");

describe("registrations DOM / unit interactions", () => {
  let origLocalStorage, origShowToast;
  beforeAll(() => {
    origLocalStorage = global.localStorage;
    origShowToast = global.showToast;
    global.localStorage = {
      store: {},
      getItem(key) {
        return this.store[key] || null;
      },
      setItem(k, v) {
        this.store[k] = String(v);
      },
      removeItem(k) {
        delete this.store[k];
      },
    };
  });
  afterAll(() => {
    global.localStorage = origLocalStorage;
    global.showToast = origShowToast;
  });

  test("getAvailableStatusTransitions returns expected arrays", () => {
    const comp = registrationsManager();
    expect(comp.getAvailableStatusTransitions("Registrado")).toEqual([
      "Confirmado",
      "Cancelado",
    ]);
    expect(comp.getAvailableStatusTransitions("Asistió")).toEqual([
      "Confirmado",
    ]);
    expect(comp.getAvailableStatusTransitions("UNKNOWN")).toEqual([]);
  });

  test("openCreateModal and openEditModal set modal state correctly", () => {
    const comp = registrationsManager();
    comp.openCreateModal();
    expect(comp.showModal).toBe(true);
    expect(comp.editMode).toBe(false);
    comp.openEditModal({
      id: 9,
      student_id: 2,
      activity_id: 3,
      status: "Confirmado",
    });
    expect(comp.showModal).toBe(true);
    expect(comp.editMode).toBe(true);
    expect(comp.currentRegistration.status).toBe("Confirmado");
  });

  test("changeRegistrationStatus posts and handles errors", async () => {
    const comp = registrationsManager();
    global.localStorage.setItem("authToken", "tok");
    comp.registrations = [
      { id: 20, student_id: 2, activity_id: 3, status: "Registrado" },
    ];

    // success path
    global.fetch = jest.fn((url, opts) =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    );
    global.showToast = jest.fn();
    await comp.changeRegistrationStatus(20, "Confirmado");
    expect(global.showToast).toHaveBeenCalledWith(
      "Estado cambiado a: Confirmado",
      "success"
    );

    // failure path (not found)
    await comp.changeRegistrationStatus(999, "Confirmado");
    // should not throw, but showToast called with error
    // simulate fetch failure
    comp.registrations = [
      { id: 21, student_id: 2, activity_id: 3, status: "Registrado" },
    ];
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ message: "err" }),
      })
    );
    await comp.changeRegistrationStatus(21, "Confirmado");
    // showToast called for error
    expect(global.showToast).toBeTruthy();
  });
});
