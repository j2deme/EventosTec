/** Tests for admin students component */

/** @jest-environment jsdom */
jest.resetModules();

const studentsAdmin = require("../students");

describe("studentsAdmin", () => {
  let mgr;
  let fetchMock;

  beforeEach(() => {
    // Setup global mocks
    global.localStorage = {
      getItem: jest.fn(),
      setItem: jest.fn(),
      removeItem: jest.fn(),
    };

    if (typeof window === "undefined") global.window = {};
    window.localStorage = global.localStorage;
    window.showToast = jest.fn();
    window.getAuthHeaders = jest.fn(() => ({
      Authorization: "Bearer test-token",
      "Content-Type": "application/json",
    }));

    // Mock fetch
    fetchMock = jest.fn();
    global.fetch = fetchMock;

    mgr = studentsAdmin();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test("initializes with correct default state", () => {
    expect(mgr.students).toEqual([]);
    expect(mgr.loading).toBe(false);
    expect(mgr.filters.search).toBe("");
    expect(mgr.filters.event_id).toBeNull();
    expect(mgr.showDetailModal).toBe(false);
  });

  test("loadStudents fetches and updates students list", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        students: [
          { id: 1, full_name: "John Doe", control_number: "12345" },
          { id: 2, full_name: "Jane Smith", control_number: "67890" },
        ],
        total: 2,
        pages: 1,
        current_page: 1,
      }),
    });

    await mgr.loadStudents(1);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/students"),
      expect.objectContaining({
        headers: expect.any(Object),
      }),
    );
    expect(mgr.students).toHaveLength(2);
    expect(mgr.students[0].full_name).toBe("John Doe");
    expect(mgr.loading).toBe(false);
  });

  test("applyFilters updates activities and reloads students", async () => {
    mgr.filters.event_id = 1;
    mgr.allActivities = [
      { id: 1, event_id: 1, name: "Activity 1" },
      { id: 2, event_id: 2, name: "Activity 2" },
    ];

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        students: [],
        total: 0,
        pages: 1,
        current_page: 1,
      }),
    });

    await mgr.applyFilters();

    expect(mgr.activities).toHaveLength(1);
    expect(mgr.activities[0].event_id).toBe(1);
  });

  test("viewStudentDetail opens modal and loads hours", async () => {
    const student = { id: 1, full_name: "John Doe", control_number: "12345" };

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        student: student,
        events_hours: [
          {
            event_id: 1,
            event_name: "Test Event",
            total_hours: 12.5,
            has_complementary_credit: true,
          },
        ],
      }),
    });

    await mgr.viewStudentDetail(student);

    expect(mgr.showDetailModal).toBe(true);
    expect(mgr.currentStudent).toEqual(student);
    expect(mgr.studentEventsHours).toHaveLength(1);
    expect(mgr.studentEventsHours[0].total_hours).toBe(12.5);
    expect(mgr.studentEventsHours[0].has_complementary_credit).toBe(true);
  });

  test("viewEventDetail loads activity chronology", async () => {
    mgr.currentStudent = { id: 1, full_name: "John Doe" };
    const eventData = { event_id: 1, event_name: "Test Event" };

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        total_confirmed_hours: 15.0,
        has_complementary_credit: true,
        activities: [
          {
            activity_id: 1,
            activity_name: "Activity 1",
            status: "Asistió",
            duration_hours: 8.0,
          },
          {
            activity_id: 2,
            activity_name: "Activity 2",
            status: "Asistió",
            duration_hours: 7.0,
          },
        ],
      }),
    });

    await mgr.viewEventDetail(eventData);

    expect(mgr.showEventDetailModal).toBe(true);
    expect(mgr.eventActivities).toHaveLength(2);
    expect(mgr.currentEventDetail.total_confirmed_hours).toBe(15.0);
    expect(mgr.currentEventDetail.has_complementary_credit).toBe(true);
  });

  test("clearFilters resets all filters", async () => {
    mgr.filters = {
      search: "test",
      event_id: 1,
      activity_id: 2,
      career: "Computer Science",
    };

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        students: [],
        total: 0,
        pages: 1,
        current_page: 1,
      }),
    });

    await mgr.clearFilters();

    expect(mgr.filters.search).toBe("");
    expect(mgr.filters.event_id).toBeNull();
    expect(mgr.filters.activity_id).toBeNull();
    expect(mgr.filters.career).toBe("");
  });

  test("formatDate returns formatted date", () => {
    const date = "2024-01-15T10:30:00Z";
    const formatted = mgr.formatDate(date);
    expect(formatted).toMatch(/2024/);
    expect(formatted).toMatch(/ene|jan/i);
  });

  test("getStatusBadgeClass returns correct classes", () => {
    expect(mgr.getStatusBadgeClass("Asistió")).toContain("green");
    expect(mgr.getStatusBadgeClass("Confirmado")).toContain("blue");
    expect(mgr.getStatusBadgeClass("Registrado")).toContain("yellow");
    expect(mgr.getStatusBadgeClass("Ausente")).toContain("red");
  });

  test("handles fetch errors gracefully", async () => {
    fetchMock.mockRejectedValueOnce(new Error("Network error"));

    await mgr.loadStudents(1);

    expect(mgr.errorMessage).toBeTruthy();
    expect(window.showToast).toHaveBeenCalledWith(expect.any(String), "error");
  });
});
