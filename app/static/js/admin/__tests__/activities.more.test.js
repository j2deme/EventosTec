const activitiesManager = require("../activities.js");

describe("activities additional update/delete flows", () => {
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

  test("updateActivity PUTs to endpoint and dispatches activity-updated", async () => {
    const comp = activitiesManager();
    global.localStorage.setItem("authToken", "tok");
    comp.currentActivity = {
      id: 55,
      event_id: 2,
      department: "D",
      name: "X",
      start_datetime: "2025-09-14T09:00:00",
      end_datetime: "2025-09-14T10:00:00",
      duration_hours: 1,
      activity_type: "t",
      location: "loc",
      modality: "m",
      requirements: "",
      max_capacity: 10,
    };
    // add matching event so validateActivityDates passes
    comp.events = [
      {
        id: 2,
        start_date: "2025-09-10T00:00:00",
        end_date: "2025-09-20T23:59:59",
      },
    ];
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 55 }),
    });
    const spy = jest.spyOn(global.window, "dispatchEvent");
    await comp.updateActivity();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/activities/55",
      expect.objectContaining({ method: "PUT" })
    );
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ type: "activity-updated" })
    );
    spy.mockRestore();
  });

  test("deleteActivity sends DELETE and dispatches activity-deleted", async () => {
    const comp = activitiesManager();
    global.localStorage.setItem("authToken", "tok");
    comp.activityToDelete = { id: 99 };
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    const spy = jest.spyOn(global.window, "dispatchEvent");
    await comp.deleteActivity();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/activities/99",
      expect.objectContaining({ method: "DELETE" })
    );
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ type: "activity-deleted" })
    );
    spy.mockRestore();
  });
});
