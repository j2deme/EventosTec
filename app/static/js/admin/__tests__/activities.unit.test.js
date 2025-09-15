// Ensure global helpers are available
require("../../app.js");
const activitiesManager = require("../activities.js");

describe("activitiesManager (unit)", () => {
  let mgr;
  beforeEach(() => {
    global.showToast = jest.fn();
    mgr = activitiesManager();
  });

  test("updateCalculatedDuration computes hours when valid dates", () => {
    mgr.currentActivity.start_datetime = "2025-09-01T10:00:00Z";
    mgr.currentActivity.end_datetime = "2025-09-01T12:30:00Z";
    mgr.updateCalculatedDuration();
    expect(mgr.calculatedDuration).toBeCloseTo(2.5);
  });

  test("updateCalculatedDuration sets 0 when invalid", () => {
    mgr.currentActivity.start_datetime = "";
    mgr.currentActivity.end_datetime = "";
    mgr.updateCalculatedDuration();
    expect(mgr.calculatedDuration).toBe(0);

    mgr.currentActivity.start_datetime = "2025-09-02T10:00:00Z";
    mgr.currentActivity.end_datetime = "2025-09-01T09:00:00Z";
    mgr.updateCalculatedDuration();
    expect(mgr.calculatedDuration).toBe(0);
  });

  test("updateDateLimits sets minDate/maxDate when event selected", () => {
    mgr.events = [
      {
        id: 1,
        start_date: "2025-09-01T00:00:00Z",
        end_date: "2025-09-02T00:00:00Z",
      },
    ];
    mgr.currentActivity.event_id = 1;
    mgr.updateDateLimits();
    expect(mgr.minDate).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/);
    expect(mgr.maxDate).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/);
  });

  test("validateActivityDates returns errors for various invalid scenarios", () => {
    mgr.events = [
      {
        id: 1,
        start_date: "2025-09-05T00:00:00Z",
        end_date: "2025-09-10T00:00:00Z",
      },
    ];

    // No event selected
    let res = mgr.validateActivityDates({
      event_id: 99,
      start_datetime: "",
      end_datetime: "",
    });
    expect(res).toMatch(/Por favor seleccione un evento v/);

    // Start before event start
    res = mgr.validateActivityDates({
      event_id: 1,
      start_datetime: "2025-09-01T00:00:00Z",
      end_datetime: "2025-09-06T00:00:00Z",
    });
    expect(res).toMatch(/no puede ser anterior/);

    // End after event end
    res = mgr.validateActivityDates({
      event_id: 1,
      start_datetime: "2025-09-06T00:00:00Z",
      end_datetime: "2025-09-20T00:00:00Z",
    });
    expect(res).toMatch(/no puede ser posterior/);

    // Start >= End
    res = mgr.validateActivityDates({
      event_id: 1,
      start_datetime: "2025-09-07T00:00:00Z",
      end_datetime: "2025-09-07T00:00:00Z",
    });
    expect(res).toMatch(/La fecha de inicio debe ser anterior/);

    // Valid
    res = mgr.validateActivityDates({
      event_id: 1,
      start_datetime: "2025-09-06T00:00:00Z",
      end_datetime: "2025-09-07T00:00:00Z",
    });
    expect(res).toBeNull();
  });

  test("getAvailableActivities filters out linked activities", () => {
    mgr.currentActivity.event_id = 2;
    mgr.activityRelations = [
      { id: 1, event_id: 2, related_activities: [{ id: 3 }], linked_by: [] },
      { id: 2, event_id: 2, related_activities: [], linked_by: [] },
      { id: 3, event_id: 2, related_activities: [], linked_by: [{ id: 1 }] },
      { id: 4, event_id: 999, related_activities: [], linked_by: [] },
    ];

    const avail = mgr.getAvailableActivities();
    // Only activities with event_id === currentActivity.event_id and not linked should remain (id 2)
    expect(avail.some((a) => a.id === 2)).toBe(true);
    expect(avail.some((a) => a.id === 1)).toBe(false);
    expect(avail.some((a) => a.id === 3)).toBe(false);
  });
});
