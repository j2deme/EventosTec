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
      
      expect(act1).toBeDefined();
      expect(act2).toBeDefined();
      expect(act3).toBeDefined();
      
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

  describe("Hours Compliance Report", () => {
    describe("initialization", () => {
      test("should initialize hours filters with default values", () => {
        const mgr = reportsManager();
        expect(mgr.hoursFilters).toEqual({
          event_id: "",
          career: "",
          search: "",
          min_hours: 0,
          filter_10_plus: false,
        });
        expect(mgr.hoursLoading).toBe(false);
        expect(mgr.hoursStudents).toEqual([]);
        expect(mgr.uniqueCareers).toEqual([]);
        expect(mgr.showParticipationModal).toBe(false);
      });
    });

    describe("loadCareers", () => {
      test("should load unique careers from students", async () => {
        const mockStudents = [
          { id: 1, career: "Ingeniería en Sistemas" },
          { id: 2, career: "Ingeniería Mecánica" },
          { id: 3, career: "Ingeniería en Sistemas" },
          { id: 4, career: "Ingeniería Industrial" },
        ];

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ students: mockStudents }),
        });

        const mgr = reportsManager();
        await mgr.loadCareers();

        expect(mgr.uniqueCareers).toHaveLength(3);
        expect(mgr.uniqueCareers).toContain("Ingeniería en Sistemas");
        expect(mgr.uniqueCareers).toContain("Ingeniería Mecánica");
        expect(mgr.uniqueCareers).toContain("Ingeniería Industrial");
      });

      test("should handle empty student list", async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ students: [] }),
        });

        const mgr = reportsManager();
        await mgr.loadCareers();

        expect(mgr.uniqueCareers).toEqual([]);
      });
    });

    describe("onHoursEventChange", () => {
      test("should reset filters when event changes", () => {
        const mgr = reportsManager();
        mgr.hoursFilters.event_id = "1";
        mgr.hoursFilters.career = "Ingeniería";
        mgr.hoursFilters.search = "12345";
        mgr.hoursStudents = [{ id: 1 }];

        mgr.onHoursEventChange();

        expect(mgr.hoursFilters.career).toBe("");
        expect(mgr.hoursFilters.search).toBe("");
        expect(mgr.hoursStudents).toEqual([]);
      });
    });

    describe("apply10PlusFilter", () => {
      test("should set min_hours to 10 when filter is enabled", () => {
        const mgr = reportsManager();
        mgr.hoursFilters.filter_10_plus = true;

        mgr.apply10PlusFilter();

        expect(mgr.hoursFilters.min_hours).toBe(10);
      });

      test("should reset min_hours to 0 when filter is disabled", () => {
        const mgr = reportsManager();
        mgr.hoursFilters.filter_10_plus = false;
        mgr.hoursFilters.min_hours = 10;

        mgr.apply10PlusFilter();

        expect(mgr.hoursFilters.min_hours).toBe(0);
      });
    });

    describe("generateHoursReport", () => {
      test("should generate hours report successfully", async () => {
        const mockStudents = [
          {
            id: 1,
            control_number: "18001234",
            full_name: "Ana García",
            career: "Ingeniería en Sistemas",
            total_hours: 11.5,
          },
          {
            id: 2,
            control_number: "19005678",
            full_name: "Carlos Martínez",
            career: "Ingeniería Mecánica",
            total_hours: 10.0,
          },
        ];

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ students: mockStudents, event: { id: 1, name: "Test Event" } }),
        });

        const mgr = reportsManager();
        mgr.hoursFilters.event_id = "1";

        await mgr.generateHoursReport();

        expect(mgr.hoursStudents).toEqual(mockStudents);
        expect(mgr.hoursLoading).toBe(false);
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining("/api/reports/hours_compliance")
        );
      });

      test("should require event_id", async () => {
        const mgr = reportsManager();
        mgr.hoursFilters.event_id = "";

        await mgr.generateHoursReport();

        expect(global.showToast).toHaveBeenCalledWith(
          expect.stringContaining("Selecciona un evento"),
          "error"
        );
        expect(mockFetch).not.toHaveBeenCalled();
      });

      test("should include filters in request", async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ students: [], event: { id: 1, name: "Test" } }),
        });

        const mgr = reportsManager();
        mgr.hoursFilters.event_id = "1";
        mgr.hoursFilters.career = "Ingeniería";
        mgr.hoursFilters.search = "12345";
        mgr.hoursFilters.min_hours = 10;

        await mgr.generateHoursReport();

        const callArgs = mockFetch.mock.calls[0][0];
        expect(callArgs).toContain("event_id=1");
        expect(callArgs).toContain("career=Ingenier%C3%ADa");
        expect(callArgs).toContain("search=12345");
        expect(callArgs).toContain("min_hours=10");
      });

      test("should show info toast when no students found", async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ students: [], event: { id: 1, name: "Test" } }),
        });

        const mgr = reportsManager();
        mgr.hoursFilters.event_id = "1";

        await mgr.generateHoursReport();

        expect(global.showToast).toHaveBeenCalledWith(
          expect.stringContaining("No se encontraron estudiantes"),
          "info"
        );
      });

      test("should handle API errors", async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: async () => ({ message: "Error del servidor" }),
        });

        const mgr = reportsManager();
        mgr.hoursFilters.event_id = "1";

        await mgr.generateHoursReport();

        expect(global.showToast).toHaveBeenCalledWith(
          expect.stringContaining("Error del servidor"),
          "error"
        );
      });
    });

    describe("downloadHoursExcel", () => {
      test("should download Excel file", async () => {
        const mockBlob = new Blob(["test data"], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
        
        mockFetch.mockResolvedValueOnce({
          ok: true,
          blob: async () => mockBlob,
          headers: {
            get: (name) => name === "Content-Disposition" ? 'attachment; filename="test-event_20241026.xlsx"' : null,
          },
        });

        // Mock DOM methods
        const mockCreateElement = jest.spyOn(document, "createElement");
        const mockAppendChild = jest.spyOn(document.body, "appendChild");
        const mockRemove = jest.fn();
        const mockClick = jest.fn();
        
        mockCreateElement.mockReturnValue({
          href: "",
          download: "",
          click: mockClick,
          remove: mockRemove,
        });
        mockAppendChild.mockImplementation(() => {});

        global.URL.createObjectURL = jest.fn(() => "blob:mock-url");
        global.URL.revokeObjectURL = jest.fn();

        const mgr = reportsManager();
        mgr.hoursFilters.event_id = "1";

        await mgr.downloadHoursExcel();

        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining("/api/reports/hours_compliance_excel")
        );
        expect(mockClick).toHaveBeenCalled();
        expect(mockRemove).toHaveBeenCalled();
      });

      test("should require event_id", async () => {
        const mgr = reportsManager();
        mgr.hoursFilters.event_id = "";

        await mgr.downloadHoursExcel();

        expect(global.showToast).toHaveBeenCalledWith(
          expect.stringContaining("Selecciona un evento"),
          "error"
        );
        expect(mockFetch).not.toHaveBeenCalled();
      });
    });

    describe("viewParticipationDetails", () => {
      test("should load and display participation details", async () => {
        const mockParticipations = [
          {
            id: 1,
            name: "Workshop Python",
            start_datetime: "2024-10-01T09:00:00",
            duration_hours: 3,
            activity_type: "Taller",
            status: "Confirmado",
          },
          {
            id: 2,
            name: "AI Conference",
            start_datetime: "2024-10-02T10:00:00",
            duration_hours: 8,
            activity_type: "Conferencia",
            status: "Asistió",
          },
        ];

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            student: { id: 1, control_number: "18001234", full_name: "Ana García" },
            participations: mockParticipations,
          }),
        });

        const mgr = reportsManager();
        mgr.hoursFilters.event_id = "1";
        mgr.hoursStudents = [
          { id: 1, control_number: "18001234", full_name: "Ana García" },
        ];

        await mgr.viewParticipationDetails(1);

        expect(mgr.showParticipationModal).toBe(true);
        expect(mgr.participationDetails).toEqual(mockParticipations);
        expect(mgr.totalParticipationHours).toBe(11);
        expect(mgr.currentStudent).toEqual(mgr.hoursStudents[0]);
      });

      test("should calculate total hours correctly", async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            student: { id: 1 },
            participations: [
              { duration_hours: 3 },
              { duration_hours: 5.5 },
              { duration_hours: 2.5 },
            ],
          }),
        });

        const mgr = reportsManager();
        mgr.hoursFilters.event_id = "1";

        await mgr.viewParticipationDetails(1);

        expect(mgr.totalParticipationHours).toBe(11);
      });

      test("should handle API errors", async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: async () => ({ message: "Error al obtener participaciones" }),
        });

        const mgr = reportsManager();
        mgr.hoursFilters.event_id = "1";

        await mgr.viewParticipationDetails(1);

        expect(global.showToast).toHaveBeenCalledWith(
          expect.stringContaining("Error al obtener participaciones"),
          "error"
        );
      });
    });

    describe("formatDateTime", () => {
      test("should format ISO datetime to locale string", () => {
        const mgr = reportsManager();
        const result = mgr.formatDateTime("2024-10-01T09:00:00");
        
        // Check that it returns a formatted string (exact format depends on locale)
        expect(result).toBeTruthy();
        expect(result).not.toBe("2024-10-01T09:00:00");
      });

      test("should handle null/empty strings", () => {
        const mgr = reportsManager();
        expect(mgr.formatDateTime(null)).toBe("");
        expect(mgr.formatDateTime("")).toBe("");
      });

      test("should handle invalid dates gracefully", () => {
        const mgr = reportsManager();
        const result = mgr.formatDateTime("invalid-date");
        
        // Should return the original string or empty, depending on implementation
        expect(typeof result).toBe("string");
      });
    });
  });
});
