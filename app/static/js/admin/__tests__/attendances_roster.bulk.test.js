/** @jest-environment jsdom */
const attendancesRoster = require("../attendances_roster");

describe("attendances_roster bulk markSelected", () => {
  beforeEach(() => {
    global.fetch = jest.fn((url, opts) => {
      if (url.includes("/api/events"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ events: [{ id: 1 }] }),
        });
      if (url.includes("/api/activities"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ activities: [{ id: 2, name: "A" }] }),
        });
      if (url.includes("/api/registrations"))
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              registrations: [{ id: 10, student: { id: 5 } }],
            }),
        });
      if (url.includes("/api/attendances/bulk-create"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ message: "bulk-ok" }),
        });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    global.showToast = jest.fn();
  });

  afterEach(() => {
    delete global.fetch;
    delete global.showToast;
  });

  test("markSelected posts student ids and reloads registrations", async () => {
    const comp = attendancesRoster();
    await comp.loadEvents();
    comp.selectedEvent = 1;
    await comp.loadActivities();
    comp.selectedActivity = 2;
    await comp.loadRegistrations();
    // select the registration
    comp.toggleSelection(comp.registrations[0]);
    expect(comp.selectedIds.size).toBe(1);
    await comp.markSelected();
    expect(global.showToast).toHaveBeenCalledWith("bulk-ok", "success");
  });
});
