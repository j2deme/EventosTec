/** Tests for admin calendar component */

/** @jest-environment jsdom */
jest.resetModules();

const calendarAdmin = require("../calendar");

describe("calendarAdmin", () => {
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

    mgr = calendarAdmin();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test("initializes with correct default state", () => {
    expect(mgr.loading).toBe(false);
    expect(mgr.errorMessage).toBe("");
    expect(mgr.events).toEqual([]);
    expect(mgr.selectedEventId).toBeNull();
    expect(mgr.calendar).toBeNull();
    expect(mgr.showDetail).toBe(false);
    expect(mgr.selectedActivity).toBeNull();
  });

  test("loadEvents selects first event and loads its calendar", async () => {
    const eventsPayload = {
      events: [
        { id: 7, name: "46° Aniversario" },
        { id: 1, name: "45° Aniversario" },
      ],
    };
    const calendarPayload = {
      event: { id: 7, name: "46° Aniversario" },
      days: ["2026-10-06"],
      activities: [],
      total_activities: 0,
    };

    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => eventsPayload })
      .mockResolvedValueOnce({ ok: true, json: async () => calendarPayload });

    await mgr.loadEvents();

    expect(mgr.events).toHaveLength(2);
    expect(mgr.selectedEventId).toBe("7");
    expect(mgr.calendar).toEqual(calendarPayload);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toContain("/api/events/");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/events/7/calendar");
    expect(mgr.loading).toBe(false);
  });

  test("loadEvents handles error response", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 500 });

    await mgr.loadEvents();

    expect(mgr.errorMessage).toBe("Error al cargar los eventos");
    expect(mgr.events).toEqual([]);
    expect(mgr.loading).toBe(false);
  });

  test("loadEvents with no events leaves calendar untouched", async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ events: [] }) });

    await mgr.loadEvents();

    expect(mgr.events).toEqual([]);
    expect(mgr.calendar).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test("onEventChange loads selected event calendar", async () => {
    mgr.selectedEventId = "3";
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ event: { id: 3 }, days: [], activities: [] }),
    });

    await mgr.onEventChange();

    expect(fetchMock).toHaveBeenCalledWith("/api/events/3/calendar");
    expect(mgr.calendar).not.toBeNull();
  });

  test("onEventChange with no selection does nothing", async () => {
    mgr.selectedEventId = null;
    await mgr.onEventChange();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("loadCalendar handles error response", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 404 });

    await mgr.loadCalendar(9);

    expect(mgr.errorMessage).toBe("Error al cargar el calendario");
    expect(mgr.calendar).toBeNull();
  });

  test("loadCalendar handles fetch rejection", async () => {
    fetchMock.mockRejectedValueOnce(new Error("network down"));

    await mgr.loadCalendar(9);

    expect(mgr.errorMessage).toBe("network down");
    expect(mgr.loading).toBe(false);
  });

  // --- Helpers de vista ---

  describe("view helpers", () => {
    beforeEach(() => {
      mgr.calendar = {
        event: { id: 7, name: "Test", start_date: "2026-10-06", end_date: "2026-10-08" },
        days: ["2026-10-06", "2026-10-07", "2026-10-08"],
        activities: [
          { id: 1, day: "2026-10-07", starts_at: "13:00", ends_at: "14:00", name: "AutoCAD" },
          { id: 2, day: "2026-10-07", starts_at: "09:00", ends_at: "10:00", name: "Maniobras" },
          { id: 3, day: "2026-10-20", starts_at: "08:00", ends_at: "09:00", name: "Fuera de ventana" },
          { id: 4, day: null, starts_at: null, ends_at: null, name: "Sin fecha" },
        ],
        total_activities: 4,
      };
    });

    test("dayActivities filters by day and sorts by start time", () => {
      const result = mgr.dayActivities("2026-10-07");
      expect(result).toHaveLength(2);
      expect(result[0].name).toBe("Maniobras"); // 09:00 antes que 13:00
      expect(result[1].name).toBe("AutoCAD");
    });

    test("dayActivities returns empty array for day without activities", () => {
      expect(mgr.dayActivities("2026-10-06")).toEqual([]);
    });

    test("dayActivities returns empty array when no calendar", () => {
      mgr.calendar = null;
      expect(mgr.dayActivities("2026-10-07")).toEqual([]);
    });

    test("dayCount returns number of activities of a day", () => {
      expect(mgr.dayCount("2026-10-07")).toBe(2);
      expect(mgr.dayCount("2026-10-06")).toBe(0);
    });

    test("outsideActivities returns activities outside window or without date", () => {
      const result = mgr.outsideActivities();
      expect(result.map((a) => a.id)).toEqual([3, 4]);
    });

    test("outsideActivities returns empty array when no calendar", () => {
      mgr.calendar = null;
      expect(mgr.outsideActivities()).toEqual([]);
    });

    test("dayLabel does not shift day due to UTC parsing", () => {
      // Parseo local (no UTC): "2026-10-06" siempre etiqueta el día 6
      const expected = new Date(2026, 9, 6).toLocaleDateString("es-MX", {
        weekday: "short",
        day: "numeric",
        month: "short",
      });
      expect(mgr.dayLabel("2026-10-06")).toBe(expected);
      expect(mgr.dayLabel("2026-10-06")).toContain("6");
    });

    test("dayLabel falls back gracefully on invalid input", () => {
      expect(mgr.dayLabel("no-date")).toBe("no-date");
    });

    test("typeColor maps known types and falls back for unknown", () => {
      expect(mgr.typeColor("Conferencia")).toContain("indigo");
      expect(mgr.typeColor("Taller")).toContain("emerald");
      expect(mgr.typeColor("Curso")).toContain("amber");
      expect(mgr.typeColor("Magistral")).toContain("rose");
      expect(mgr.typeColor("Otro")).toContain("slate");
      expect(mgr.typeColor(undefined)).toContain("slate");
    });

    test("cupoLabel shows registered/capacity only when capacity defined", () => {
      expect(mgr.cupoLabel({ max_capacity: 30, registered_count: 12 })).toBe("12/30");
      expect(mgr.cupoLabel({ max_capacity: null, registered_count: 5 })).toBe("");
      expect(mgr.cupoLabel({ max_capacity: 10 })).toBe("0/10");
      expect(mgr.cupoLabel(null)).toBe("");
    });

    test("gridStyle uses one column per day", () => {
      expect(mgr.gridStyle()).toContain("repeat(3,");
      mgr.calendar.days = ["2026-10-06"];
      expect(mgr.gridStyle()).toContain("repeat(1,");
      mgr.calendar = null;
      expect(mgr.gridStyle()).toContain("repeat(1,");
    });
  });

  test("openDetail and closeDetail toggle modal state", () => {
    const activity = { id: 5, name: "Rally" };
    mgr.openDetail(activity);
    expect(mgr.showDetail).toBe(true);
    expect(mgr.selectedActivity).toBe(activity);

    mgr.closeDetail();
    expect(mgr.showDetail).toBe(false);
    expect(mgr.selectedActivity).toBeNull();
  });
});
