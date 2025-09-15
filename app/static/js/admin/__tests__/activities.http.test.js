/** @jest-environment jsdom */
const activitiesManager = require("../activities");

describe("activities HTTP branches and errors", () => {
  let origFetch, origLocalStorage, origShowToast;
  beforeAll(() => {
    origFetch = global.fetch;
    origLocalStorage = global.localStorage;
    origShowToast = global.showToast;
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
    global.localStorage = origLocalStorage;
    global.showToast = origShowToast;
  });

  test("loadActivities throws when token missing (caught and sets errorMessage)", async () => {
    const comp = activitiesManager();
    // ensure no token
    global.localStorage.removeItem &&
      global.localStorage.removeItem("authToken");
    // mock fetch so it would fail if called
    global.fetch = jest.fn(() => Promise.resolve({ ok: false }));
    await comp.loadActivities();
    // when token missing the catch will set errorMessage
    expect(comp.errorMessage).toBeTruthy();
  });

  test("loadActivities handles non-ok response and sets errorMessage", async () => {
    const comp = activitiesManager();
    global.localStorage.setItem("authToken", "tok");
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: false, status: 500, statusText: "Server Error" })
    );
    await comp.loadActivities();
    expect(comp.errorMessage).toMatch(/Error al cargar actividades/);
    expect(global.showToast).toHaveBeenCalledWith(
      "Error al cargar actividades",
      "error"
    );
  });

  test("loadEvents with token fills events, and loadActivityRelations handles error", async () => {
    const comp = activitiesManager();
    global.localStorage.setItem("authToken", "tok");
    // first call to /api/events/
    global.fetch = jest.fn((url) => {
      if (url === "/api/events/")
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([{ id: 1, name: "E" }]),
        });
      if (url === "/api/activities/relations")
        return Promise.resolve({ ok: false });
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            activities: [],
            current_page: 1,
            pages: 1,
            total: 0,
          }),
      });
    });

    await comp.loadEvents();
    expect(comp.events.length).toBeGreaterThan(0);

    // loadActivityRelations should throw internally and be caught by callers; call directly to cover branch
    global.fetch = jest.fn(() => Promise.resolve({ ok: false }));
    await expect(comp.loadActivityRelations()).rejects.toThrow();
  });

  test("createActivity handles validation error from validateActivityDates", async () => {
    const comp = activitiesManager();
    global.localStorage.setItem("authToken", "tok");
    // set events so validateActivityDates fails (no matching event)
    comp.events = [];
    comp.currentActivity = {
      event_id: 999,
      start_datetime: "2025-09-01T10:00",
      end_datetime: "2025-09-01T12:00",
    };

    global.fetch = jest.fn();
    await comp.createActivity();
    expect(comp.errorMessage).toBeTruthy();
  });
});
