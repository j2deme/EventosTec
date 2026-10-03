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

  // ---------------------------------------------------------------------
  // Créditos complementarios multi-evento y overrides
  // ---------------------------------------------------------------------

  test("loadComplementaryCredits sends event_ids and stores stats", async () => {
    mgr.exportFilters = { event_ids: [1, 3], career: "" };

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        students: [
          {
            id: 9,
            control_number: "A1",
            total_hours: 10,
            hours_by_event: { 1: 6, 3: 4 },
          },
        ],
        events: [
          { id: 1, name: "Ev 1" },
          { id: 3, name: "Ev 3" },
        ],
        excluded_already_credited: 2,
        excluded_by_override: 1,
      }),
    });

    await mgr.loadComplementaryCredits();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const url = fetchMock.mock.calls[0][0];
    expect(url).toContain("/api/students/complementary-credits?");
    expect(url).toContain("event_ids=");
    expect(mgr.exportData).toHaveLength(1);
    expect(mgr.exportStats.events).toHaveLength(2);
    expect(mgr.exportStats.excluded_already_credited).toBe(2);
    expect(mgr.exportStats.excluded_by_override).toBe(1);
    expect(mgr.loadingExport).toBe(false);
  });

  test("loadComplementaryCredits requires at least one event", async () => {
    mgr.exportFilters = { event_ids: [], career: "" };

    await mgr.loadComplementaryCredits();

    expect(mgr.exportError).toContain("al menos un evento");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("toggleExportEvent adds/removes events and resets results", () => {
    mgr.exportFilters = { event_ids: [1], career: "" };
    mgr.exportData = [{ id: 9 }];
    mgr.exportStats = {
      events: [{ id: 1, name: "Ev 1" }],
      excluded_already_credited: 1,
      excluded_by_override: 0,
    };

    mgr.toggleExportEvent(2);
    expect(mgr.exportFilters.event_ids).toEqual([1, 2]);
    expect(mgr.exportData).toEqual([]);
    expect(mgr.exportStats.events).toEqual([]);

    mgr.toggleExportEvent(1);
    expect(mgr.exportFilters.event_ids).toEqual([2]);
  });

  test("hoursInEvent formats hours per event breakdown", () => {
    const student = { hours_by_event: { 1: 6, 3: 4.25 } };
    expect(mgr.hoursInEvent(student, 1)).toBe("6.0");
    expect(mgr.hoursInEvent(student, 3)).toBe("4.3");
    expect(mgr.hoursInEvent(student, 9)).toBe("0.0");
    expect(mgr.hoursInEvent(null, 1)).toBe("0.0");
    expect(mgr.hoursInEvent({}, 1)).toBe("0.0");
  });

  test("openExportModal preselects filter event and loads overrides", async () => {
    mgr.filters.event_id = 7;
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ overrides: [], total: 0 }),
    });

    await mgr.openExportModal();

    expect(mgr.showExportModal).toBe(true);
    expect(mgr.exportFilters.event_ids).toEqual([7]);
    expect(mgr.creditOverrides).toEqual([]);
  });

  test("setCreditOverride posts and refreshes list and overrides", async () => {
    mgr.exportFilters = { event_ids: [1], career: "" };

    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          overrides: [{ student_id: 5, decision: "exclude", reason: null }],
          total: 1,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ students: [], events: [] }),
      });

    await mgr.setCreditOverride(5, "exclude");

    expect(fetchMock.mock.calls[0][0]).toBe("/api/students/credit-overrides");
    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({ method: "POST" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      student_id: 5,
      decision: "exclude",
    });
    expect(mgr.creditOverrides).toHaveLength(1);
    expect(mgr.hasCreditOverride(5)).toBe(true);
    expect(mgr.hasCreditOverride(6)).toBe(false);
  });

  test("removeCreditOverride deletes and refreshes", async () => {
    mgr.exportFilters = { event_ids: [1], career: "" };

    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ overrides: [], total: 0 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ students: [], events: [] }),
      });

    await mgr.removeCreditOverride(5);

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/students/credit-overrides/5",
    );
    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(mgr.creditOverrides).toEqual([]);
  });

  test("loadCreditOverrides tolerates backend errors (tabla pendiente)", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ message: "Error" }),
    });

    await mgr.loadCreditOverrides();

    expect(mgr.creditOverrides).toEqual([]);
    expect(window.showToast).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------------
  // Descarga autenticada del Excel y otorgamiento de crédito (Fase 3)
  // ---------------------------------------------------------------------

  // Prepara el <a> temporal que downloadCreditsExcel pulsa al final
  function mockDownloadDom() {
    const mockClick = jest.fn();
    const mockRemove = jest.fn();
    const createElement = jest
      .spyOn(document, "createElement")
      .mockReturnValue({
        href: "",
        download: "",
        click: mockClick,
        remove: mockRemove,
      });
    const appendChild = jest
      .spyOn(document.body, "appendChild")
      .mockImplementation(() => {});
    global.URL.createObjectURL = jest.fn(() => "blob:mock-url");
    global.URL.revokeObjectURL = jest.fn();
    return {
      mockClick,
      restore() {
        createElement.mockRestore();
        appendChild.mockRestore();
        delete global.URL.createObjectURL;
        delete global.URL.revokeObjectURL;
      },
    };
  }

  // Respuesta binaria del endpoint /complementary-credits/export
  function blobResponse(filename) {
    return {
      ok: true,
      blob: async () => new Blob(["xlsx"]),
      headers: {
        get: (name) =>
          name === "Content-Disposition" && filename
            ? `attachment; filename="${filename}"`
            : null,
      },
    };
  }

  test("exportToExcel descarga con fetch autenticado, no window.open", async () => {
    window.open = jest.fn();
    mgr.exportFilters = { event_ids: [2, 4], career: "Ing" };
    fetchMock.mockResolvedValueOnce(blobResponse("creditos.xlsx"));
    const dom = mockDownloadDom();

    try {
      await mgr.exportToExcel();

      // La ruta exige header Authorization: window.open abriría la URL sin
      // token y el backend respondería 401 en la pestaña nueva.
      expect(window.open).not.toHaveBeenCalled();
      const url = fetchMock.mock.calls[0][0];
      expect(url).toContain("/api/students/complementary-credits/export?");
      expect(url).toContain("event_ids=2%2C4");
      expect(url).toContain("career=Ing");
      expect(dom.mockClick).toHaveBeenCalled();
      expect(mgr.exportingExcel).toBe(false);
    } finally {
      dom.restore();
    }
  });

  test("loadComplementaryCredits envía include_granted y guarda el contador", async () => {
    mgr.exportFilters = { event_ids: [1], career: "" };
    mgr.includeGranted = true;

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        students: [{ id: 9, already_granted: true }],
        events: [{ id: 1, name: "Ev 1" }],
        excluded_already_granted: 3,
        credit_grants_available: true,
      }),
    });

    await mgr.loadComplementaryCredits();

    expect(fetchMock.mock.calls[0][0]).toContain("include_granted=1");
    expect(mgr.exportStats.excluded_already_granted).toBe(3);
    expect(mgr.creditGrantsAvailable).toBe(true);
    // La única fila está acreditada → 0 pendientes de otorgar
    expect(mgr.pendingGrantCount()).toBe(0);
  });

  test("grantCredits descarga primero y después registra el lote", async () => {
    mgr.exportFilters = { event_ids: [5], career: "" };
    mgr.exportData = [{ id: 9, already_granted: false }];
    window.confirm = jest.fn(() => true);

    fetchMock
      .mockResolvedValueOnce(blobResponse("creditos.xlsx"))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          batch_id: "b1",
          granted_students: 1,
          granted_events: 1,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          students: [],
          events: [],
          excluded_already_credited: 0,
          excluded_by_override: 0,
          excluded_already_granted: 1,
          credit_grants_available: true,
        }),
      });
    const dom = mockDownloadDom();

    try {
      await mgr.grantCredits();

      expect(window.confirm).toHaveBeenCalledTimes(1);
      expect(fetchMock).toHaveBeenCalledTimes(3);

      // 1) el archivo va primero: si falla, no se registró nada
      expect(fetchMock.mock.calls[0][0]).toContain(
        "/api/students/complementary-credits/export?",
      );
      // 2) solo después se registra el otorgamiento
      expect(fetchMock.mock.calls[1][0]).toBe("/api/students/credit-grants");
      expect(fetchMock.mock.calls[1][1]).toEqual(
        expect.objectContaining({ method: "POST" }),
      );
      expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
        event_ids: [5],
        career: "",
        confirm: true,
      });
      expect(window.showToast).toHaveBeenCalledWith(
        expect.stringContaining("Crédito otorgado"),
        "success",
      );
      // 3) la lista se refresca: los acreditados salen de pendientes
      expect(mgr.exportStats.excluded_already_granted).toBe(1);
      expect(mgr.granting).toBe(false);
    } finally {
      dom.restore();
    }
  });

  test("grantCredits no hace nada si el usuario cancela la confirmación", async () => {
    mgr.exportFilters = { event_ids: [5], career: "" };
    mgr.exportData = [{ id: 9, already_granted: false }];
    window.confirm = jest.fn(() => false);

    await mgr.grantCredits();

    expect(window.confirm).toHaveBeenCalledTimes(1);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(mgr.granting).toBe(false);
  });

  test("grantCredits se bloquea sin la migración credit_grants", async () => {
    mgr.creditGrantsAvailable = false;
    mgr.exportFilters = { event_ids: [5], career: "" };
    mgr.exportData = [{ id: 9, already_granted: false }];
    window.confirm = jest.fn(() => true);

    await mgr.grantCredits();

    // Ni confirmar ni descargar: el archivo no podría registrarse
    expect(window.confirm).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(window.showToast).toHaveBeenCalledWith(
      expect.stringContaining("migración"),
      "error",
    );
  });

  test("grantCredits avisa si el registro falla tras descargar", async () => {
    mgr.exportFilters = { event_ids: [5], career: "" };
    mgr.exportData = [{ id: 9, already_granted: false }];
    window.confirm = jest.fn(() => true);

    fetchMock
      .mockResolvedValueOnce(blobResponse("creditos.xlsx"))
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ message: "Tabla credit_grants no existe" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ students: [], events: [] }),
      });
    const dom = mockDownloadDom();

    try {
      await mgr.grantCredits();

      expect(window.showToast).toHaveBeenCalledWith(
        expect.stringContaining("no se registró"),
        "error",
      );
      expect(mgr.granting).toBe(false);
    } finally {
      dom.restore();
    }
  });

  test("searchOverrideStudent prefers exact control number match", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        students: [
          { id: 11, control_number: "A002", full_name: "Otro" },
          { id: 12, control_number: "A001", full_name: "Exacta" },
        ],
      }),
    });

    mgr.overrideSearch = "a001";
    await mgr.searchOverrideStudent();

    expect(mgr.overrideSearchResult.id).toBe(12);
    expect(mgr.overrideSearchError).toBe("");
    expect(mgr.searchingOverride).toBe(false);
  });

  test("searchOverrideStudent sets error when no results", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ students: [] }),
    });

    mgr.overrideSearch = "ZZZ999";
    await mgr.searchOverrideStudent();

    expect(mgr.overrideSearchResult).toBeNull();
    expect(mgr.overrideSearchError).toBe("Sin resultados");
  });

  test("includeOverrideFromSearch posts include override", async () => {
    mgr.overrideSearchResult = {
      id: 33,
      control_number: "X1",
      full_name: "Forzada",
    };
    mgr.exportFilters = { event_ids: [1], career: "" };

    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ overrides: [], total: 0 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ students: [], events: [] }),
      });

    await mgr.includeOverrideFromSearch();

    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      student_id: 33,
      decision: "include",
    });
    expect(mgr.overrideSearch).toBe("");
    expect(mgr.overrideSearchResult).toBeNull();
  });
});
