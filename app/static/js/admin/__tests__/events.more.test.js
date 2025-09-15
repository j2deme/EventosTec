const eventsManager = require("../events.js");

describe("eventsManager additional flows and error handling", () => {
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

  test("updateEvent makes PUT and dispatches event-updated on success", async () => {
    const comp = eventsManager();
    global.localStorage.setItem("authToken", "t");
    comp.currentEvent = {
      id: 7,
      name: "X",
      description: "",
      start_date: "2025-09-10T00:00:00",
      end_date: "2025-09-11T00:00:00",
      is_active: true,
    };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 7 }),
    });
    const spy = jest.spyOn(global.window, "dispatchEvent");
    await comp.updateEvent();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/events/7",
      expect.objectContaining({ method: "PUT" })
    );
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ type: "event-updated" })
    );
    spy.mockRestore();
  });

  test("deleteEvent makes DELETE and dispatches event-deleted on success", async () => {
    const comp = eventsManager();
    global.localStorage.setItem("authToken", "t");
    comp.eventToDelete = { id: 13 };
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    const spy = jest.spyOn(global.window, "dispatchEvent");
    await comp.deleteEvent();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/events/13",
      expect.objectContaining({ method: "DELETE" })
    );
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ type: "event-deleted" })
    );
    spy.mockRestore();
  });

  test("loadEvents handles network error (fetch rejects) gracefully", async () => {
    const comp = eventsManager();
    global.localStorage.setItem("authToken", "t");
    global.fetch.mockRejectedValueOnce(new Error("network fail"));
    await comp.loadEvents();
    expect(global.showToast).toHaveBeenCalledWith(expect.any(String), "error");
    expect(comp.loading).toBe(false);
  });
});
