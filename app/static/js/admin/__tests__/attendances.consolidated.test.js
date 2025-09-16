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
});
