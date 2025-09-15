const activitiesManager = require("../activities.js");

describe("activities fetch interactions", () => {
  let origFetch;
  let origLs;
  beforeEach(() => {
    origFetch = global.fetch;
    global.fetch = jest.fn();
    // mock localStorage
    origLs = global.localStorage;
    global.localStorage = {
      _store: {},
      getItem(key) {
        return this._store[key] || null;
      },
      setItem(key, val) {
        this._store[key] = String(val);
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

  test("loadEvents fetches events and stores them", async () => {
    const comp = activitiesManager();
    global.localStorage.setItem("authToken", "token123");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [{ id: 1, name: "E1" }],
    });
    await comp.loadEvents();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/events/",
      expect.any(Object)
    );
    expect(comp.events.length).toBeGreaterThan(0);
  });

  test("loadActivities fetches paginated activities and sets pagination", async () => {
    const comp = activitiesManager();
    global.localStorage.setItem("authToken", "tok");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        activities: [
          {
            id: 11,
            start_datetime: "2025-09-14T08:00:00Z",
            end_datetime: "2025-09-14T10:00:00Z",
          },
        ],
        current_page: 1,
        pages: 1,
        total: 1,
      }),
    });
    await comp.loadActivities(1);
    expect(global.fetch).toHaveBeenCalled();
    expect(comp.activities[0].id).toBe(11);
    expect(comp.pagination.total).toBe(1);
  });

  test("createActivity posts data and triggers activity-created event on success", async () => {
    const comp = activitiesManager();
    global.localStorage.setItem("authToken", "tok");
    // fill currentActivity minimal
    comp.currentActivity = {
      id: null,
      event_id: 2,
      department: "D",
      name: "N",
      description: "desc",
      start_datetime: "2025-09-14T09:00:00",
      end_datetime: "2025-09-14T11:00:00",
      duration_hours: 2,
      activity_type: "type",
      location: "loc",
      modality: "in-person",
      requirements: "",
      max_capacity: 10,
    };
    // añadir evento correspondiente para que validateActivityDates no falle
    comp.events = [
      {
        id: 2,
        start_date: "2025-09-10T00:00:00",
        end_date: "2025-09-20T23:59:59",
      },
    ];

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 99 }),
    });

    // spy on dispatchEvent
    const spy = jest.spyOn(global.window, "dispatchEvent");
    await comp.createActivity();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/activities/",
      expect.objectContaining({ method: "POST" })
    );
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ type: "activity-created" })
    );
    spy.mockRestore();
  });
});
