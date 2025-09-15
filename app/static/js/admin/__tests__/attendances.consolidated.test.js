const attendancesList = require("../attendances_list");
const { mockFetchFactory, setupLocalStorage } = require("../../testUtils");

describe("attendances consolidated tests", () => {
  afterEach(() => {
    delete global.fetch;
  });

  test("loadEvents and loadAttendances populate arrays and date parsing", async () => {
    const events = [{ id: 2, name: "Event 2" }];
    const attendances = [
      {
        id: 1,
        student_name: "S1",
        activity_name: "A1",
        event_name: "E1",
        check_in: "2025-01-01T08:00:00",
      },
    ];

    global.fetch = mockFetchFactory({
      "/api/events": { ok: true, json: () => Promise.resolve(events) },
      "/api/attendances": {
        ok: true,
        json: () => Promise.resolve(attendances),
      },
    });

    const comp = attendancesList();
    await comp.loadEvents();
    await comp.loadAttendances();

    expect(comp.events).toEqual(events);
    expect(comp.attendances.length).toBe(1);
    expect(comp.attendances[0].date).toBe("2025-01-01");
  });

  test("clearFilters resets and reloads attendances", async () => {
    global.fetch = mockFetchFactory({
      "/api/events": {
        ok: true,
        json: () => Promise.resolve([{ id: 1, name: "E" }]),
      },
      "/api/attendances": {
        ok: true,
        json: () =>
          Promise.resolve([
            {
              id: 1,
              student_name: "S",
              activity_name: "A",
              activity: { name: "A", event: { name: "E" } },
              check_in: "2025-01-01T08:00:00",
            },
          ]),
      },
    });

    const comp = attendancesList();
    comp.selectedEvent = 1;
    comp.selectedActivity = 2;
    comp.selectedStudent = { id: 3 };
    comp.studentQuery = "X";
    await comp.clearFilters();

    expect(comp.selectedEvent).toBe("");
    expect(comp.selectedActivity).toBe("");
    expect(comp.selectedStudent).toBeNull();
    expect(comp.studentQuery).toBe("");
  });
});
