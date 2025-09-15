const activitiesManager = require("../activities.js");

describe("activitiesManager helper methods", () => {
  test("formatDateTimeForInput produces expected format", () => {
    const comp = activitiesManager();
    const dt = "2025-09-14T08:30:00Z"; // UTC
    const result = comp.formatDateTimeForInput(dt);
    // Should produce YYYY-MM-DDTHH:MM in local tz; just assert pattern
    expect(result).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/);
  });

  test("updateCalculatedDuration computes hours between datetimes", () => {
    const comp = activitiesManager();
    comp.currentActivity.start_datetime = "2025-09-14T08:00:00";
    comp.currentActivity.end_datetime = "2025-09-14T10:30:00";
    comp.updateCalculatedDuration();
    expect(comp.calculatedDuration).toBeGreaterThan(2);
    // approx 2.5 hours
    expect(Math.abs(comp.calculatedDuration - 2.5)).toBeLessThan(0.01);
  });

  test("validateActivityDates enforces event bounds and ordering", () => {
    const comp = activitiesManager();
    // Evento con rango 2025-09-10 -> 2025-09-20
    comp.events = [
      {
        id: 1,
        start_date: "2025-09-10T00:00:00",
        end_date: "2025-09-20T23:59:59",
      },
    ];

    // Caso válido
    const activityValid = {
      event_id: 1,
      start_datetime: "2025-09-12T09:00:00",
      end_datetime: "2025-09-12T11:00:00",
    };
    expect(comp.validateActivityDates(activityValid)).toBeNull();

    // Inicio anterior al evento
    const activityEarly = {
      event_id: 1,
      start_datetime: "2025-09-09T09:00:00",
      end_datetime: "2025-09-12T11:00:00",
    };
    expect(comp.validateActivityDates(activityEarly)).toMatch(
      /no puede ser anterior/
    );

    // Fin posterior al evento
    const activityLate = {
      event_id: 1,
      start_datetime: "2025-09-19T09:00:00",
      end_datetime: "2025-09-21T11:00:00",
    };
    expect(comp.validateActivityDates(activityLate)).toMatch(
      /no puede ser posterior/
    );

    // Inicio >= fin
    const activityBadOrder = {
      event_id: 1,
      start_datetime: "2025-09-15T12:00:00",
      end_datetime: "2025-09-15T12:00:00",
    };
    expect(comp.validateActivityDates(activityBadOrder)).toMatch(
      /inicio debe ser anterior/
    );
  });

  test("getAvailableActivities filters out linked activities", () => {
    const comp = activitiesManager();
    comp.currentActivity.event_id = 100;
    comp.activityRelations = [
      { id: 1, event_id: 100, related_activities: [{ id: 3 }], linked_by: [] },
      { id: 2, event_id: 100, related_activities: [], linked_by: [] },
      { id: 3, event_id: 100, related_activities: [], linked_by: [] },
      { id: 4, event_id: 200, related_activities: [], linked_by: [] },
    ];
    const avail = comp.getAvailableActivities();
    // should exclude id 1 and 3 because they are linked; include id 2 only (event_id match)
    expect(avail.map((a) => a.id)).toEqual([2]);
  });
});
