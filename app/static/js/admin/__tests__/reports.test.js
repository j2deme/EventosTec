// app/static/js/admin/__tests__/reports.test.js

describe("reportsManager", () => {
  let mockFetch, reportsManager;

  beforeEach(() => {
    jest.resetModules();
    
    // Mock global.fetch antes de requerir el módulo
    mockFetch = jest.fn();
    global.fetch = mockFetch;
    global.safeFetch = mockFetch;
    global.showToast = jest.fn();
    
    // Requerir el módulo después de mockear
    reportsManager = require("../reports.js");
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe("initialization", () => {
    test("should initialize with default values", () => {
      const mgr = reportsManager();
      expect(mgr.events).toEqual([]);
      expect(mgr.activities).toEqual([]);
      expect(mgr.filters).toEqual({
        event_id: "",
        activity_id: "",
        department: "",
      });
      expect(mgr.loading).toBe(false);
      expect(mgr.matrix).toBeNull();
    });

    test("init should call loadEvents and loadActivities", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ events: [], activities: [] }),
      });

      const mgr = reportsManager();
      const loadEventsSpy = jest.spyOn(mgr, "loadEvents");
      const loadActivitiesSpy = jest.spyOn(mgr, "loadActivities");

      await mgr.init();

      expect(loadEventsSpy).toHaveBeenCalled();
      expect(loadActivitiesSpy).toHaveBeenCalled();
    });
  });

  describe("loadEvents", () => {
    test("should load events from API", async () => {
      const mockEvents = [
        { id: 1, name: "Event 1" },
        { id: 2, name: "Event 2" },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ events: mockEvents }),
      });

      const mgr = reportsManager();
      await mgr.loadEvents();

      expect(mockFetch).toHaveBeenCalledWith("/api/events?per_page=1000");
      expect(mgr.events).toEqual(mockEvents);
    });

    test("should handle errors when loading events", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Network error"));

      const consoleErrorSpy = jest
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const mgr = reportsManager();
      await mgr.loadEvents();

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Error loading events",
        expect.any(Error)
      );
      expect(mgr.events).toEqual([]);
    });

    test("should handle non-ok response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      const mgr = reportsManager();
      await mgr.loadEvents();

      expect(mgr.events).toEqual([]);
    });
  });

  describe("loadActivities", () => {
    test("should load activities and extract departments", async () => {
      const mockActivities = [
        { id: 1, name: "Activity 1", department: "CS" },
        { id: 2, name: "Activity 2", department: "EE" },
        { id: 3, name: "Activity 3", department: "CS" },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ activities: mockActivities }),
      });

      const mgr = reportsManager();
      await mgr.loadActivities();

      expect(mgr.activities).toEqual(mockActivities);
      expect(mgr.departments).toContain("CS");
      expect(mgr.departments).toContain("EE");
      expect(mgr.departments.length).toBe(2);
    });

    test("should sort departments alphabetically", async () => {
      const mockActivities = [
        { id: 1, department: "ZZ" },
        { id: 2, department: "AA" },
        { id: 3, department: "MM" },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ activities: mockActivities }),
      });

      const mgr = reportsManager();
      await mgr.loadActivities();

      expect(mgr.departments).toEqual(["AA", "MM", "ZZ"]);
    });

    test("should handle errors when loading activities", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Network error"));

      const consoleErrorSpy = jest
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const mgr = reportsManager();
      await mgr.loadActivities();

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Error loading activities",
        expect.any(Error)
      );
      expect(mgr.activities).toEqual([]);
    });
  });

  describe("filterActivities", () => {
    test("should return all activities when no event filter", () => {
      const mgr = reportsManager();
      mgr.activities = [
        { id: 1, event_id: 1 },
        { id: 2, event_id: 2 },
      ];

      mgr.filterActivities();

      expect(mgr.activitiesFiltered).toHaveLength(2);
    });

    test("should filter activities by event_id", () => {
      const mgr = reportsManager();
      mgr.activities = [
        { id: 1, event_id: 1 },
        { id: 2, event_id: 2 },
        { id: 3, event_id: 1 },
      ];
      mgr.filters.event_id = "1";

      mgr.filterActivities();

      expect(mgr.activitiesFiltered).toHaveLength(2);
      expect(mgr.activitiesFiltered[0].event_id).toBe(1);
      expect(mgr.activitiesFiltered[1].event_id).toBe(1);
    });

    test("should handle event object with nested id", () => {
      const mgr = reportsManager();
      mgr.activities = [
        { id: 1, event: { id: 1 } },
        { id: 2, event: { id: 2 } },
      ];
      mgr.filters.event_id = "1";

      mgr.filterActivities();

      expect(mgr.activitiesFiltered).toHaveLength(1);
    });
  });

  describe("onEventChange", () => {
    test("should reset activity_id and filter activities", () => {
      const mgr = reportsManager();
      mgr.filters.activity_id = "5";
      mgr.filters.event_id = "1";
      mgr.activities = [{ id: 1, event_id: 1 }];
      const filterSpy = jest.spyOn(mgr, "filterActivities");

      mgr.onEventChange();

      expect(mgr.filters.activity_id).toBe("");
      expect(filterSpy).toHaveBeenCalled();
    });
  });

  describe("generateMatrix", () => {
    test("should generate participation matrix", async () => {
      const mockResponse = {
        careers: ["ISC", "IIA"],
        generations: ["2023", "2024"],
        semesters: [1, 2, 3],
        matrix: {},
        matrix_semester: {
          ISC: { 1: 5, 2: 3, 3: 2 },
          IIA: { 1: 4, 2: 6, 3: 1 },
        },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const mgr = reportsManager();
      mgr.filters.event_id = "1";

      await mgr.generateMatrix();

      expect(mgr.loading).toBe(false);
      expect(mgr.careers).toEqual(["ISC", "IIA"]);
      expect(mgr.generations).toEqual(["2023", "2024"]);
      expect(mgr.semesters).toEqual([1, 2, 3]);
      expect(mgr.rowSubtotals).toHaveProperty("ISC");
      expect(mgr.rowSubtotals.ISC).toBe(10); // 5+3+2
      expect(mgr.rowSubtotals.IIA).toBe(11); // 4+6+1
      expect(mgr.totalSumSemesters).toBe(21);
    });

    test("should set loading state correctly", async () => {
      mockFetch.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            setTimeout(
              () =>
                resolve({
                  ok: true,
                  json: async () => ({
                    careers: [],
                    generations: [],
                    matrix: {},
                  }),
                }),
              10
            );
          })
      );

      const mgr = reportsManager();
      const promise = mgr.generateMatrix();

      expect(mgr.loading).toBe(true);

      await promise;

      expect(mgr.loading).toBe(false);
    });

    test("should handle errors and show toast", async () => {
      mockFetch.mockRejectedValueOnce(new Error("API error"));

      const consoleErrorSpy = jest
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const mgr = reportsManager();

      await mgr.generateMatrix();

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Error generating matrix",
        expect.any(Error)
      );
      expect(global.showToast).toHaveBeenCalledWith(
        "Error generando matriz",
        "error"
      );
      expect(mgr.loading).toBe(false);
    });

    test("should include filters in request params", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ careers: [], generations: [], matrix: {} }),
      });

      const mgr = reportsManager();
      mgr.filters.event_id = "1";
      mgr.filters.department = "CS";
      mgr.filters.activity_id = "5";

      await mgr.generateMatrix();

      const callArgs = mockFetch.mock.calls[0][0];
      expect(callArgs).toContain("event_id=1");
      expect(callArgs).toContain("department=CS");
      expect(callArgs).toContain("activity_id=5");
    });
  });

  describe("generateFillReport", () => {
    test("should generate fill report with normalized data", async () => {
      const mockResponse = {
        activities: [
          {
            id: 1,
            name: "Activity 1",
            status: "available",
            percent: 75.5,
          },
          {
            id: 2,
            name: "Activity 2",
            status: "full",
            percent: 100,
          },
          {
            id: 3,
            name: "Activity 3",
            status: "unlimited",
            percent: null,
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const mgr = reportsManager();
      await mgr.generateFillReport();

      expect(mgr.fillLoading).toBe(false);
      expect(mgr.fillReport).toHaveLength(3);
      // Find activities by id to avoid order issues
      const act1 = mgr.fillReport.find(a => a.id === 1);
      const act2 = mgr.fillReport.find(a => a.id === 2);
      const act3 = mgr.fillReport.find(a => a.id === 3);
      
      expect(act1.percent).toBe(76); // 75.5 rounded
      expect(act1.status_label).toBe("Disponible");
      expect(act2.status_label).toBe("Lleno");
      expect(act2.percent).toBe(100);
      expect(act3.percent).toBeNull();
      expect(act3.status_label).toBe("Abierto");
    });

    test("should handle errors in fill report", async () => {
      mockFetch.mockRejectedValueOnce(new Error("API error"));

      const consoleErrorSpy = jest
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const mgr = reportsManager();

      await mgr.generateFillReport();

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Error generating fill report",
        expect.any(Error)
      );
      expect(mgr.fillLoading).toBe(false);
      expect(mgr.fillReport).toEqual([]);
    });

    test("should include filters in fill report request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ activities: [] }),
      });

      const mgr = reportsManager();
      mgr.filters.event_id = "2";
      mgr.filters.activity_id = "10";
      mgr.filters.department = "EE";

      await mgr.generateFillReport();

      const callArgs = mockFetch.mock.calls[0][0];
      expect(callArgs).toContain("event_id=2");
      expect(callArgs).toContain("activity_id=10");
      expect(callArgs).toContain("department=EE");
      expect(callArgs).toContain("include_unlimited=1");
    });
  });

  describe("formatSemester", () => {
    test("should format numeric semesters", () => {
      const mgr = reportsManager();
      expect(mgr.formatSemester(1)).toBe("1o");
      expect(mgr.formatSemester(2)).toBe("2o");
      expect(mgr.formatSemester("3")).toBe("3o");
    });

    test("should handle null and undefined", () => {
      const mgr = reportsManager();
      expect(mgr.formatSemester(null)).toBe("");
      expect(mgr.formatSemester(undefined)).toBe("");
    });

    test("should handle non-numeric values", () => {
      const mgr = reportsManager();
      expect(mgr.formatSemester("N/A")).toBe("N/A");
      expect(mgr.formatSemester("Otro")).toBe("Otro");
    });
  });
});
