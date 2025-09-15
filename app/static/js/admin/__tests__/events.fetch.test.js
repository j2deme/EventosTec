const eventsManager = require("../events.js");

describe("eventsManager fetch interactions", () => {
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

  test("loadEvents fetches and populates events", async () => {
    const comp = eventsManager();
    global.localStorage.setItem("authToken", "tkn");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        events: [
          {
            id: 1,
            start_date: "2025-09-10T00:00:00",
            end_date: "2025-09-12T00:00:00",
          },
        ],
        current_page: 1,
        pages: 1,
        total: 1,
      }),
    });
    await comp.loadEvents();
    expect(global.fetch).toHaveBeenCalled();
    expect(comp.events.length).toBe(1);
  });

  test("createEvent posts and dispatches event-created", async () => {
    const comp = eventsManager();
    global.localStorage.setItem("authToken", "tkn");
    comp.currentEvent = {
      name: "X",
      description: "",
      start_date: "2025-09-10T00:00:00",
      end_date: "2025-09-11T00:00:00",
      is_active: true,
    };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 55 }),
    });
    const spy = jest.spyOn(global.window, "dispatchEvent");
    await comp.createEvent();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/events",
      expect.objectContaining({ method: "POST" })
    );
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ type: "event-created" })
    );
    spy.mockRestore();
  });
});
