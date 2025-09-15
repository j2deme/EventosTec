const attendancesList = require("../attendances_list");
const { mockFetchFactory } = require("../../testUtils");

describe("attendances_list response wrapper handling", () => {
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

    const comp = attendancesList();
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

    const comp = attendancesList();
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

    const comp = attendancesList();
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

    const comp = attendancesList();
    await comp.loadAttendances();

    expect(Array.isArray(comp.attendances)).toBe(true);
    expect(comp.attendances.length).toBe(0);
  });
});
