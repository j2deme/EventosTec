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

  // Formato canónico: numérico 24 h ("08/10/2026, 09:05"), sin AM/PM
  test("formatStamp formatea date_display en 24 h sin AM/PM", () => {
    const a = attendancesAdmin();
    const out = a.formatStamp("2026-10-08 09:05");
    expect(out).toMatch(/\d{2}\/\d{2}\/\d{4}/);
    expect(out).toMatch(/09:05/);
    expect(out).not.toMatch(/\bAM\b|\bPM\b|a\. m\.|p\. m\./i);
  });

  test("formatStamp preserva '—' y devuelve cadena para entradas no parseables", () => {
    const a = attendancesAdmin();
    expect(a.formatStamp("—")).toBe("—");
    expect(a.formatStamp("")).toBe("");
    expect(a.formatStamp(null)).toBe("");
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
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
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

    const result = a.attendancesTableFiltered();
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({
      id: 1,
      student_name: "John",
      activity_id: 10,
      key: 1,
      __selected_for_sync: false,
    });
    expect(result[1]).toEqual({
      id: 2,
      student_name: "Jane",
      activity_id: 20,
      key: 2,
      __selected_for_sync: false,
    });
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
    expect(filtered[0]).toEqual({
      id: 1,
      student_name: "John",
      activity_id: 10,
      key: 1,
      __selected_for_sync: false,
    });
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
    expect(filtered[0]).toEqual({
      id: 2,
      student_name: "Jane",
      registration_id: null,
      key: 2,
      __selected_for_sync: false,
    });
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
    expect(filtered[0]).toEqual({
      id: 1,
      student_name: "John Doe",
      student_identifier: "12345",
      activity_name: "Workshop",
      key: 1,
      __selected_for_sync: false,
    });
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
    expect(filtered[0]).toEqual({
      id: 2,
      student_name: "Jane Smith",
      student_identifier: "67890",
      activity_name: "Conference",
      key: 2,
      __selected_for_sync: false,
    });
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
    expect(filtered[0]).toEqual({
      id: 2,
      student_name: "Jane Smith",
      student_identifier: "67890",
      activity_name: "Conference",
      key: 2,
      __selected_for_sync: false,
    });
  });
});

describe("attendancesAdmin batch checkout — hora real de cierre", () => {
  test("batchActualEndDefault usa el fin programado si aún no pasó", () => {
    const a = attendancesAdmin();
    a.batchActivityId = 7;
    a.activities = [{ id: 7, end_datetime: "2099-10-08T13:00:00+00:00" }];

    const out = a.batchActualEndDefault();
    // Formato de <input type="datetime-local">, en hora local
    expect(out).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
    const end = new Date("2099-10-08T13:00:00+00:00");
    expect(new Date(out).getTime()).toBeGreaterThanOrEqual(
      end.getTime() - 60000,
    );
  });

  test("batchActualEndDefault usa la hora actual si el evento ya terminó", () => {
    const a = attendancesAdmin();
    a.batchActivityId = 7;
    a.activities = [{ id: 7, end_datetime: "2020-01-01T00:00:00+00:00" }];

    const out = a.batchActualEndDefault();
    // Recortado al minuto: no puede quedar antes de "ahora"
    expect(new Date(out).getTime()).toBeGreaterThanOrEqual(Date.now() - 120000);
  });

  test("batchActualEndDefault acepta el id explícito (cambio del select)", () => {
    const a = attendancesAdmin();
    a.batchActivityId = "";
    a.activities = [{ id: 9, end_datetime: "2099-01-01T10:00:00+00:00" }];

    expect(a.batchActualEndDefault(9)).toMatch(/T\d{2}:\d{2}$/);
    expect(a.batchActualEndDefault("desconocido")).toMatch(/T\d{2}:\d{2}$/);
  });

  test("openBatchCheckoutModal prellena la hora de cierre con la actividad filtrada", () => {
    const a = attendancesAdmin();
    a.filters = { activity_id: 3, event_id: "" };
    a.activities = [{ id: 3, end_datetime: "2099-10-08T13:00:00+00:00" }];

    a.openBatchCheckoutModal();

    expect(a.showBatchCheckoutModal).toBe(true);
    expect(a.batchActualEnd).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
  });

  test("performBatchCheckout envía actual_end_time en el payload", async () => {
    const a = attendancesAdmin();
    a.batchEventId = 1;
    a.batchActivityId = 2;
    a.batchDryRun = true;
    a.batchActualEnd = "2026-10-08T13:15";
    a.sf = jest.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({ summary: { processed: 1 } }),
      }),
    );

    await a.performBatchCheckout();

    expect(a.sf).toHaveBeenCalledWith("/api/attendances/batch-checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        activity_id: 2,
        dry_run: true,
        actual_end_time: "2026-10-08T13:15",
      }),
    });
    expect(a.batchResult).toEqual({ processed: 1 });
  });

  test("performBatchCheckout omite actual_end_time cuando el campo está vacío", async () => {
    const a = attendancesAdmin();
    a.batchEventId = 1;
    a.batchActivityId = 2;
    a.batchDryRun = true;
    a.batchActualEnd = "";
    a.sf = jest.fn(() =>
      Promise.resolve({ json: () => Promise.resolve({ summary: {} }) }),
    );

    await a.performBatchCheckout();

    const body = JSON.parse(a.sf.mock.calls[0][1].body);
    expect(body.actual_end_time).toBeNull();
  });
});
