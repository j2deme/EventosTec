const attendancesRoster = require("../attendances_roster");

describe("attendancesRoster factory", () => {
  let origFetch, origShowToast, origWindowOpen;

  beforeAll(() => {
    origFetch = global.fetch;
    origShowToast = global.showToast;
    origWindowOpen = global.window?.open;
  });
  afterAll(() => {
    global.fetch = origFetch;
    global.showToast = origShowToast;
    if (global.window) global.window.open = origWindowOpen;
  });

  test("loadEvents fills events and printRoster opens window", async () => {
    global.fetch = jest.fn((url) => {
      if (url.includes("/api/events"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ events: [{ id: 5, name: "E5" }] }),
        });
      if (url.includes("/api/activities"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ activities: [{ id: 8, name: "A8" }] }),
        });
      if (url.includes("/api/registrations"))
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              registrations: [
                { id: 100, student: { id: 1, full_name: "María" } },
              ],
            }),
        });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    global.showToast = jest.fn();
    // mock window.open
    if (!global.window) global.window = {};
    global.window.open = jest.fn(() => ({
      document: { write: jest.fn(), close: jest.fn() },
      print: jest.fn(),
    }));

    const comp = attendancesRoster();
    await comp.loadEvents();
    expect(comp.events.length).toBeGreaterThan(0);

    comp.activities = [{ id: 8, name: "A8" }];
    comp.selectedActivity = 8;
    await comp.loadRegistrations();
    expect(comp.registrations.length).toBe(1);

    comp.printRoster();
    expect(global.window.open).toHaveBeenCalled();
  });
});
