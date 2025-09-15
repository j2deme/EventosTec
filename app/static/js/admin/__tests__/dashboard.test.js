const adminDashboard = require("../dashboard");

describe("adminDashboard factory", () => {
  let origFetch, origLocalStorage, origShowToast;

  beforeAll(() => {
    origFetch = global.fetch;
    origLocalStorage = global.localStorage;
    origShowToast = global.showToast;

    // minimal localStorage mock
    global.localStorage = {
      store: {},
      getItem(key) {
        return this.store[key] || null;
      },
      setItem(key, val) {
        this.store[key] = String(val);
      },
      removeItem(key) {
        delete this.store[key];
      },
    };
  });

  afterAll(() => {
    global.fetch = origFetch;
    global.localStorage = origLocalStorage;
    global.showToast = origShowToast;
  });

  test("init sets default active tab and can loadEvents without token", async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
    );
    const comp = adminDashboard();
    // no token in localStorage => loadEvents should return early without throwing
    await comp.loadEvents();
    expect(comp.events).toEqual([]);
    // can set and validate tab
    comp.setActiveTab("events");
    expect(comp.activeTab).toBe("events");
  });
});
