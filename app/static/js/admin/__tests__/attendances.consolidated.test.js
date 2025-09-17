const { attendancesAdmin } = require("../attendances.js");

describe("attendancesAdmin helpers", () => {
  test("parseAttendancesPayload returns array unchanged", () => {
    const a = attendancesAdmin();
    const arr = [1, 2, 3];
    expect(a.parseAttendancesPayload(arr)).toEqual(arr);
  });

  test("parseAttendancesPayload extracts attendances or data fields", () => {
    const a = attendancesAdmin();
    expect(a.parseAttendancesPayload({ attendances: [4, 5] })).toEqual([4, 5]);
    expect(a.parseAttendancesPayload({ data: [6] })).toEqual([6]);
  });

  test("parseAttendancesPayload returns empty array for falsy payload", () => {
    const a = attendancesAdmin();
    expect(a.parseAttendancesPayload(null)).toEqual([]);
    expect(a.parseAttendancesPayload(undefined)).toEqual([]);
  });

  test("sf uses window.safeFetch when available", async () => {
    const a = attendancesAdmin();
    global.safeFetch = jest.fn(() => Promise.resolve("ok"));
    await a.sf("/test-safe", { method: "GET" });
    expect(global.safeFetch).toHaveBeenCalledWith("/test-safe", {
      method: "GET",
    });
    delete global.safeFetch;
  });

  test("sf falls back to global.fetch when safeFetch is not defined", async () => {
    const a = attendancesAdmin();
    global.fetch = jest.fn(() => Promise.resolve("ok"));
    // Ensure safeFetch is not present
    delete global.safeFetch;
    await a.sf("/test-fetch", { method: "POST" });
    expect(global.fetch).toHaveBeenCalledWith("/test-fetch", {
      method: "POST",
    });
    delete global.fetch;
  });

  test("submitAssign returns early when selectedActivity or selectedStudent missing", async () => {
    const a = attendancesAdmin();
    // ensure no selection
    a.selectedActivity = null;
    a.selectedStudent = null;

    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    );
    await a.submitAssign();
    // fetch should not be called because submitAssign returns early
    expect(global.fetch).not.toHaveBeenCalled();
    delete global.fetch;
  });

  test("filteredActivities returns all activities when no filters", () => {
    const a = attendancesAdmin();
    a.activities = [
      { id: 1, name: "Act 1", event_id: 10, type: "workshop" },
      { id: 2, name: "Act 2", event_id: 20, type: "conference" },
    ];
    a.filters = { event_id: "", activity_type: "" };

    expect(a.filteredActivities()).toEqual(a.activities);
  });

  test("filteredActivities filters by event_id", () => {
    const a = attendancesAdmin();
    a.activities = [
      { id: 1, name: "Act 1", event_id: 10, type: "workshop" },
      { id: 2, name: "Act 2", event_id: 20, type: "conference" },
      { id: 3, name: "Act 3", event_id: 10, type: "seminar" },
    ];
    a.filters = { event_id: "10", activity_type: "" };

    const filtered = a.filteredActivities();
    expect(filtered).toHaveLength(2);
    expect(filtered.map((a) => a.id)).toEqual([1, 3]);
  });

  test("filteredActivities filters by activity_type", () => {
    const a = attendancesAdmin();
    a.activities = [
      { id: 1, name: "Act 1", event_id: 10, type: "workshop" },
      { id: 2, name: "Act 2", event_id: 20, type: "conference" },
      { id: 3, name: "Act 3", event_id: 10, type: "workshop" },
    ];
    a.filters = { event_id: "", activity_type: "workshop" };

    const filtered = a.filteredActivities();
    expect(filtered).toHaveLength(2);
    expect(filtered.map((a) => a.id)).toEqual([1, 3]);
  });

  test("filteredActivities combines event_id and activity_type filters", () => {
    const a = attendancesAdmin();
    a.activities = [
      { id: 1, name: "Act 1", event_id: 10, type: "workshop" },
      { id: 2, name: "Act 2", event_id: 20, type: "workshop" },
      { id: 3, name: "Act 3", event_id: 10, type: "conference" },
    ];
    a.filters = { event_id: "10", activity_type: "workshop" };

    const filtered = a.filteredActivities();
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe(1);
  });

  test("attendancesTableFiltered returns all attendances when no filters", () => {
    const a = attendancesAdmin();
    a.attendances = [
      { id: 1, student_name: "John", activity_id: 10 },
      { id: 2, student_name: "Jane", activity_id: 20 },
    ];
    a.filters = {
      search: "",
      activity_id: "",
      only_without_registration: false,
      activity_type: "",
    };

    expect(a.attendancesTableFiltered()).toEqual(a.attendances);
  });

  test("attendancesTableFiltered filters by activity_id", () => {
    const a = attendancesAdmin();
    a.attendances = [
      { id: 1, student_name: "John", activity_id: 10 },
      { id: 2, student_name: "Jane", activity_id: 20 },
    ];
    a.filters = {
      search: "",
      activity_id: "10",
      only_without_registration: false,
      activity_type: "",
    };

    const filtered = a.attendancesTableFiltered();
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe(1);
  });

  test("attendancesTableFiltered filters by only_without_registration", () => {
    const a = attendancesAdmin();
    a.attendances = [
      { id: 1, student_name: "John", registration_id: 100 },
      { id: 2, student_name: "Jane", registration_id: null },
    ];
    a.filters = {
      search: "",
      activity_id: "",
      only_without_registration: true,
      activity_type: "",
    };

    const filtered = a.attendancesTableFiltered();
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe(2);
  });

  test("attendancesTableFiltered filters by search text", () => {
    const a = attendancesAdmin();
    a.attendances = [
      {
        id: 1,
        student_name: "John Doe",
        student_identifier: "12345",
        activity_name: "Workshop",
      },
      {
        id: 2,
        student_name: "Jane Smith",
        student_identifier: "67890",
        activity_name: "Conference",
      },
    ];
    a.filters = {
      search: "john",
      activity_id: "",
      only_without_registration: false,
      activity_type: "",
    };

    const filtered = a.attendancesTableFiltered();
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe(1);
  });

  test("attendancesTableFiltered search matches student_identifier", () => {
    const a = attendancesAdmin();
    a.attendances = [
      {
        id: 1,
        student_name: "John Doe",
        student_identifier: "12345",
        activity_name: "Workshop",
      },
      {
        id: 2,
        student_name: "Jane Smith",
        student_identifier: "67890",
        activity_name: "Conference",
      },
    ];
    a.filters = {
      search: "678",
      activity_id: "",
      only_without_registration: false,
      activity_type: "",
    };

    const filtered = a.attendancesTableFiltered();
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe(2);
  });

  test("attendancesTableFiltered search matches activity_name", () => {
    const a = attendancesAdmin();
    a.attendances = [
      {
        id: 1,
        student_name: "John Doe",
        student_identifier: "12345",
        activity_name: "Workshop",
      },
      {
        id: 2,
        student_name: "Jane Smith",
        student_identifier: "67890",
        activity_name: "Conference",
      },
    ];
    a.filters = {
      search: "conf",
      activity_id: "",
      only_without_registration: false,
      activity_type: "",
    };

    const filtered = a.attendancesTableFiltered();
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe(2);
  });
});
