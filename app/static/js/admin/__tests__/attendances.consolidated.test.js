// Consolidated tests for attendances_list (merged from multiple small files)

jest.resetModules();

const attendancesListFactory = require("../attendances.js").attendancesList;
const { mockFetchFactory } = require("../../testUtils");

describe("attendancesList consolidated", () => {
  let origFetch;
  let mgr;

  beforeEach(() => {
    origFetch = global.fetch;
    global.showToast = jest.fn();
    mgr = attendancesListFactory();
  });

  afterEach(() => {
    global.fetch = origFetch;
    jest.restoreAllMocks();
    try {
      delete global.fetch;
    } catch (e) {
      /* ignore */
    }
  });

  test("searchStudents with short query clears results", async () => {
    mgr.studentQuery = "a";
    await mgr.searchStudents();
    expect(mgr.studentResults).toEqual([]);
  });

  test("searchStudents with long query calls fetch and sets results", async () => {
    mgr.studentQuery = "juan";
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve([{ id: 5, full_name: "Juan Perez" }]),
      })
    );
    await mgr.searchStudents();
    expect(global.fetch).toHaveBeenCalledWith(
      `/api/students/search?q=${encodeURIComponent(mgr.studentQuery)}`
    );
    expect(mgr.studentResults.length).toBe(1);
    expect(mgr.studentResults[0].full_name).toBe("Juan Perez");
  });

  test("selectStudent sets fields and calls loadAttendances", async () => {
    const spy = jest.spyOn(mgr, "loadAttendances").mockResolvedValue();
    const student = { id: 9, full_name: "Ana" };
    await mgr.selectStudent(student);
    expect(mgr.selectedStudent).toBe(student);
    expect(mgr.studentQuery).toBe("Ana");
    expect(mgr.studentResults).toEqual([]);
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });

  test("clearFilters resets filters and calls loadAttendances", async () => {
    mgr.selectedEvent = 1;
    mgr.selectedActivity = 2;
    mgr.selectedStudent = { id: 3 };
    mgr.studentQuery = "X";
    const spy = jest.spyOn(mgr, "loadAttendances").mockResolvedValue();
    await mgr.clearFilters();
    expect(mgr.selectedEvent).toBe("");
    expect(mgr.selectedActivity).toBe("");
    expect(mgr.selectedStudent).toBeNull();
    expect(mgr.studentQuery).toBe("");
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });

  test("loadActivities without selectedEvent calls loadAttendances immediately", async () => {
    mgr.selectedEvent = "";
    const spy = jest.spyOn(mgr, "loadAttendances").mockResolvedValue();
    await mgr.loadActivities();
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });

  test("loadActivities with selectedEvent fetches activities and calls loadAttendances", async () => {
    mgr.selectedEvent = 4;
    global.fetch = jest.fn((url) => {
      if (url.startsWith("/api/activities"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([{ id: 7, name: "Act" }]),
        });
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });
    const spy = jest.spyOn(mgr, "loadAttendances");
    await mgr.loadActivities();
    // Accept additional query params (e.g., for_student) — ensure base call was made
    expect(global.fetch).toHaveBeenCalled();
    const calledUrl = global.fetch.mock.calls[0][0];
    expect(
      calledUrl.startsWith(`/api/activities?event_id=${mgr.selectedEvent}`)
    ).toBe(true);
    expect(mgr.activities.length).toBe(1);
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });

  test("loadEvents fetches and sets events", async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve([{ id: 100, name: "E" }]),
      })
    );
    await mgr.loadEvents();
    expect(global.fetch).toHaveBeenCalledWith("/api/events");
    expect(mgr.events.length).toBe(1);
  });

  test("loadAttendances maps different shapes (array + nested) and sets attendances", async () => {
    const sample = [
      {
        id: 1,
        student: { full_name: "S1" },
        activity: { name: "A1", event: { name: "Ev1" } },
        check_in: "2025-09-01T10:00:00Z",
        status: "present",
      },
    ];
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(sample) })
    );
    await mgr.loadAttendances();
    expect(mgr.attendances.length).toBe(1);
    expect(mgr.attendances[0].student_name).toBe("S1");
    expect(mgr.attendances[0].activity_name).toBe("A1");
    expect(mgr.attendances[0].event_name).toBe("Ev1");
    expect(mgr.attendances[0].date).toBe("2025-09-01");
  });

  describe("response wrapper handling", () => {
    afterEach(() => {
      delete global.fetch;
    });

    test("handles direct array response", async () => {
      const attendances = [
        { id: 1, student_name: "Alice", check_in: "2025-01-01T08:00:00" },
      ];

      global.fetch = mockFetchFactory({
        "/api/attendances": {
          ok: true,
          json: () => Promise.resolve(attendances),
        },
      });

      const comp = attendancesListFactory();
      await comp.loadAttendances();

      expect(comp.attendances.length).toBe(1);
      expect(comp.attendances[0].student_name).toBe("Alice");
      expect(comp.attendances[0].date).toBe("2025-01-01");
    });

    test("handles { attendances: [...] } wrapper", async () => {
      const attendances = [
        { id: 2, student_name: "Bob", check_in: "2025-02-02T09:00:00" },
      ];

      global.fetch = mockFetchFactory({
        "/api/attendances": {
          ok: true,
          json: () => Promise.resolve({ attendances }),
        },
      });

      const comp = attendancesListFactory();
      await comp.loadAttendances();

      expect(comp.attendances.length).toBe(1);
      expect(comp.attendances[0].student_name).toBe("Bob");
    });

    test("handles { data: [...] } wrapper", async () => {
      const attendances = [
        { id: 3, student_name: "Carol", check_in: "2025-03-03T10:00:00" },
      ];

      global.fetch = mockFetchFactory({
        "/api/attendances": {
          ok: true,
          json: () => Promise.resolve({ data: attendances }),
        },
      });

      const comp = attendancesListFactory();
      await comp.loadAttendances();

      expect(comp.attendances.length).toBe(1);
      expect(comp.attendances[0].student_name).toBe("Carol");
    });

    test("handles unexpected non-array response gracefully", async () => {
      global.fetch = mockFetchFactory({
        "/api/attendances": {
          ok: true,
          json: () => Promise.resolve({ error: "not found" }),
        },
      });

      const comp = attendancesListFactory();
      await comp.loadAttendances();

      expect(Array.isArray(comp.attendances)).toBe(true);
      expect(comp.attendances.length).toBe(0);
    });
  });
});
