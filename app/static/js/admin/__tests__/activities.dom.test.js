/** @jest-environment jsdom */
const activitiesManager = require("../activities");

describe("activities DOM / unit interactions", () => {
  let origLocalStorage, origShowToast;

  beforeAll(() => {
    origLocalStorage = global.localStorage;
    origShowToast = global.showToast;
    // minimal localStorage mock
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

  test("updateCalculatedDuration computes hours correctly", () => {
    const comp = activitiesManager();
    comp.currentActivity.start_datetime = "2025-09-14T08:00";
    comp.currentActivity.end_datetime = "2025-09-14T10:30";
    comp.updateCalculatedDuration();
    // 2.5 hours
    expect(comp.calculatedDuration).toBeCloseTo(2.5, 5);
  });

  test("updateDateLimits sets minDate/maxDate from selected event", () => {
    const comp = activitiesManager();
    comp.events = [
      {
        id: 1,
        start_date: "2025-09-01T00:00:00",
        end_date: "2025-09-30T23:59:00",
      },
    ];
    comp.currentActivity.event_id = 1;
    comp.updateDateLimits();
    expect(comp.minDate).toMatch(/^2025-09-01T/);
    expect(comp.maxDate).toMatch(/^2025-09-30T/);
  });

  test("validateActivityDates returns correct errors and null when valid", () => {
    const comp = activitiesManager();
    comp.events = [
      {
        id: 2,
        start_date: "2025-09-10T08:00:00",
        end_date: "2025-09-20T18:00:00",
      },
    ];

    // Missing event -> error
    let err = comp.validateActivityDates({
      event_id: 999,
      start_datetime: "2025-09-12T09:00",
      end_datetime: "2025-09-12T11:00",
    });
    expect(err).toBeDefined();

    // Start before event
    err = comp.validateActivityDates({
      event_id: 2,
      start_datetime: "2025-09-09T09:00",
      end_datetime: "2025-09-12T11:00",
    });
    expect(err).toMatch(/no puede ser anterior/);

    // End after event
    err = comp.validateActivityDates({
      event_id: 2,
      start_datetime: "2025-09-12T09:00",
      end_datetime: "2025-09-21T11:00",
    });
    expect(err).toMatch(/no puede ser posterior/);

    // start >= end
    err = comp.validateActivityDates({
      event_id: 2,
      start_datetime: "2025-09-12T12:00",
      end_datetime: "2025-09-12T12:00",
    });
    expect(err).toMatch(/La fecha de inicio debe ser anterior/);

    // valid
    err = comp.validateActivityDates({
      event_id: 2,
      start_datetime: "2025-09-12T09:00",
      end_datetime: "2025-09-12T11:00",
    });
    expect(err).toBeNull();
  });

  test("openCreateModal sets showModal and defaults", () => {
    const comp = activitiesManager();
    comp.openCreateModal();
    expect(comp.showModal).toBe(true);
    expect(comp.currentActivity.id).toBeNull();
    expect(comp.calculatedDuration).toBe(0);
  });

  test("createActivity makes POST and dispatches event on success", async () => {
    const comp = activitiesManager();
    // prepare localStorage token
    global.localStorage.setItem("authToken", "tok");
    // prepare event so validateActivityDates passes
    comp.events = [
      {
        id: 10,
        start_date: "2025-09-01T00:00:00",
        end_date: "2025-09-30T23:59:00",
      },
    ];
    comp.currentActivity = {
      event_id: 10,
      department: "D",
      name: "N",
      description: "",
      start_datetime: "2025-09-12T09:00",
      end_datetime: "2025-09-12T11:00",
      duration_hours: "",
      activity_type: "",
      location: "",
      modality: "",
      requirements: "",
      max_capacity: null,
    };

    // mock fetch for POST and subsequent GET (loadActivities)
    global.fetch = jest.fn((url, opts) => {
      if (url === "/api/activities/" && opts && opts.method === "POST") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ id: 555 }),
        });
      }
      if (url && url.startsWith("/api/activities?")) {
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
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const dispatchSpy = jest.spyOn(window, "dispatchEvent");
    global.showToast = jest.fn();

    await comp.createActivity();

    expect(dispatchSpy).toHaveBeenCalled();
    expect(global.showToast).toHaveBeenCalledWith(
      "Actividad creada exitosamente",
      "success"
    );
  });
});
