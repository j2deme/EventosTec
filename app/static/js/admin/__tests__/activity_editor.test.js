// app/static/js/admin/__tests__/activity_editor.test.js

describe("activityEditorManager", () => {
  let mockFetch, activityEditorManager;

  beforeEach(() => {
    jest.resetModules();

    // Mock global.fetch antes de requerir el módulo
    mockFetch = jest.fn();
    global.fetch = mockFetch;
    global.safeFetch = mockFetch;
    global.showToast = jest.fn();

    // Requerir el módulo después de mockear
    activityEditorManager = require("../activity_editor.js");
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe("initialization", () => {
    test("should initialize with default values", () => {
      const mgr = activityEditorManager();
      expect(mgr.visible).toBe(false);
      expect(mgr.loading).toBe(false);
      expect(mgr.saving).toBe(false);
      expect(mgr.errorMessage).toBe("");
      expect(mgr.editingActivity).toBe(false);
      expect(mgr.currentActivity).toHaveProperty("id", null);
      expect(mgr.currentActivity).toHaveProperty("name", "");
    });

    test("init should register event listener", () => {
      const addEventListenerSpy = jest.spyOn(window, "addEventListener");
      const mgr = activityEditorManager();

      mgr.init();

      expect(addEventListenerSpy).toHaveBeenCalledWith(
        "open-activity-editor",
        expect.any(Function),
      );
    });
  });

  describe("loadActivity", () => {
    test("should load activity successfully", async () => {
      const mockActivity = {
        id: 1,
        name: "Test Activity",
        event_id: 1,
        department: "CS",
        speakers: ["Speaker 1", "Speaker 2"],
        target_audience: {
          general: true,
          careers: ["ISC", "IIA"],
        },
        knowledge_area: "Math",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ activity: mockActivity }),
      });

      const mgr = activityEditorManager();
      await mgr.loadActivity(1);

      expect(mgr.loading).toBe(false);
      expect(mgr.editingActivity).toBe(true);
      expect(mgr.currentActivity.name).toBe("Test Activity");
      expect(mgr.currentActivity.speakersList).toEqual([
        "Speaker 1",
        "Speaker 2",
      ]);
      expect(mgr.currentActivity.target_audience_general).toBe(true);
      expect(mgr.currentActivity.target_audience_careersList).toEqual([
        "ISC",
        "IIA",
      ]);
      expect(mgr.currentActivity.knowledge_area).toBe("Math");
    });

    test("should handle activity without target_audience", async () => {
      const mockActivity = {
        id: 2,
        name: "Activity 2",
        speakers: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ activity: mockActivity }),
      });

      const mgr = activityEditorManager();
      await mgr.loadActivity(2);

      expect(mgr.currentActivity.target_audience_general).toBe(false);
      expect(mgr.currentActivity.target_audience_careersList).toEqual([]);
      expect(mgr.currentActivity.speakersList).toEqual([]);
    });

    test("should handle error when loading activity", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      const consoleErrorSpy = jest
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const mgr = activityEditorManager();

      await mgr.loadActivity(999);

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Error loading activity in editor:",
        expect.any(Error),
      );
      expect(mgr.errorMessage).toContain("Error al cargar actividad");
      expect(global.showToast).toHaveBeenCalledWith(
        expect.stringContaining("Error"),
        "error",
      );
      expect(mgr.loading).toBe(false);
    });

    test("should load events if not loaded", async () => {
      const mockActivity = { id: 1, name: "Test" };
      const mockEvents = [{ id: 1, name: "Event 1" }];

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ activity: mockActivity }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ events: mockEvents }),
        });

      const mgr = activityEditorManager();
      mgr.events = [];

      await mgr.loadActivity(1);

      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(mockFetch).toHaveBeenCalledWith("/api/events/");
      expect(mgr.events).toEqual(mockEvents);
    });
  });

  describe("loadEvents", () => {
    test("should load events successfully", async () => {
      const mockEvents = [
        { id: 1, name: "Event 1" },
        { id: 2, name: "Event 2" },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ events: mockEvents }),
      });

      const mgr = activityEditorManager();
      await mgr.loadEvents();

      expect(mgr.events).toEqual(mockEvents);
    });

    test("should handle array response", async () => {
      const mockEvents = [{ id: 1, name: "Event 1" }];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockEvents,
      });

      const mgr = activityEditorManager();
      await mgr.loadEvents();

      expect(mgr.events).toEqual(mockEvents);
    });

    test("should handle error when loading events", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      const consoleErrorSpy = jest
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const mgr = activityEditorManager();

      await mgr.loadEvents();

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Error loading events in editor:",
        expect.any(Error),
      );
      expect(mgr.events).toEqual([]);
    });
  });

  describe("resetCurrent", () => {
    test("should reset currentActivity to defaults", () => {
      const mgr = activityEditorManager();
      mgr.currentActivity = {
        id: 5,
        name: "Test",
        department: "CS",
      };
      mgr.errorMessage = "Some error";

      mgr.resetCurrent();

      expect(mgr.currentActivity.id).toBeNull();
      expect(mgr.currentActivity.name).toBe("");
      expect(mgr.currentActivity.department).toBe("");
      expect(mgr.currentActivity.duration_hours).toBe(1.0);
      expect(mgr.errorMessage).toBe("");
    });
  });

  describe("saveActivity", () => {
    test("should require event_id before saving", async () => {
      const mgr = activityEditorManager();
      mgr.currentActivity.event_id = "";
      mgr.currentActivity.name = "Test Activity";

      await mgr.saveActivity();

      expect(mgr.errorMessage).toContain("Selecciona un evento");
      expect(global.showToast).toHaveBeenCalledWith(
        expect.stringContaining("evento"),
        "error",
      );
      expect(mockFetch).not.toHaveBeenCalled();
    });

    test("should create new activity (POST)", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: 1, name: "New Activity" }),
      });

      const mgr = activityEditorManager();
      mgr.editingActivity = false;
      mgr.currentActivity = {
        id: null,
        event_id: 1,
        department: "CS",
        name: "New Activity",
        description: "Test description",
        start_datetime: "2024-01-01T10:00",
        end_datetime: "2024-01-01T12:00",
        duration_hours: 2.0,
        activity_type: "Taller",
        location: "Room 101",
        modality: "Presencial",
        requirements: "None",
        knowledge_area: "Math",
        speakersList: ["Speaker 1"],
        target_audience_general: true,
        target_audience_careersList: ["ISC"],
        max_capacity: 30,
      };

      const dispatchEventSpy = jest.spyOn(window, "dispatchEvent");

      await mgr.saveActivity();

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/activities/",
        expect.objectContaining({
          method: "POST",
          body: expect.any(String),
        }),
      );
      expect(mgr.saving).toBe(false);
      expect(mgr.visible).toBe(false);
      expect(global.showToast).toHaveBeenCalledWith(
        "Actividad creada",
        "success",
      );
      expect(dispatchEventSpy).toHaveBeenCalledWith(
        expect.objectContaining({ type: "activity-saved" }),
      );
    });

    test("should update existing activity (PUT)", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ activity: { id: 5 } }),
      });

      const mgr = activityEditorManager();
      mgr.editingActivity = true;
      mgr.currentActivity = {
        id: 5,
        event_id: 1,
        department: "CS",
        name: "Updated Activity",
        description: "",
        start_datetime: "2024-01-01T10:00",
        end_datetime: "2024-01-01T12:00",
        duration_hours: 2.0,
        activity_type: "Conferencia",
        location: "Room 102",
        modality: "Híbrido",
        requirements: "",
        knowledge_area: "",
        speakersList: [],
        target_audience_general: false,
        target_audience_careersList: [],
        max_capacity: null,
      };

      await mgr.saveActivity();

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/activities/5",
        expect.objectContaining({
          method: "PUT",
          body: expect.any(String),
        }),
      );
      expect(global.showToast).toHaveBeenCalledWith(
        "Actividad actualizada",
        "success",
      );
    });

    test("should handle error when saving activity", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ message: "Validation error" }),
      });

      const consoleErrorSpy = jest
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const mgr = activityEditorManager();
      mgr.currentActivity.event_id = 1;
      mgr.currentActivity.name = "Test";

      await mgr.saveActivity();

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Error saving activity:",
        expect.any(Error),
      );
      expect(mgr.errorMessage).toContain("Validation error");
      expect(global.showToast).toHaveBeenCalledWith(
        "Validation error",
        "error",
      );
      expect(mgr.saving).toBe(false);
    });

    test("should construct proper payload with all fields", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: 1 }),
      });

      const mgr = activityEditorManager();
      mgr.currentActivity = {
        id: null,
        event_id: "1",
        department: "CS",
        name: "Test",
        description: "Desc",
        start_datetime: "2024-01-01T10:00",
        end_datetime: "2024-01-01T12:00",
        duration_hours: "2.5",
        activity_type: "Taller",
        location: "Room",
        modality: "Presencial",
        requirements: "Req",
        knowledge_area: "Math",
        speakersList: ["S1", "S2"],
        target_audience_general: true,
        target_audience_careersList: ["ISC"],
        max_capacity: "50",
      };

      await mgr.saveActivity();

      const callArgs = mockFetch.mock.calls[0];
      const payload = JSON.parse(callArgs[1].body);

      expect(payload.event_id).toBe(1);
      expect(payload.duration_hours).toBe(2.5);
      expect(payload.max_capacity).toBe(50);
      expect(payload.speakers).toEqual(["S1", "S2"]);
      expect(payload.target_audience).toEqual({
        general: true,
        careers: ["ISC"],
      });
    });
  });

  describe("close", () => {
    test("should close editor and reset", () => {
      const mgr = activityEditorManager();
      mgr.visible = true;
      mgr.currentActivity.name = "Test";

      mgr.close();

      expect(mgr.visible).toBe(false);
      expect(mgr.currentActivity.name).toBe("");
    });
  });

  describe("event listener integration", () => {
    test("should open editor for editing when event is dispatched", async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ activity: { id: 1, name: "Test" } }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ events: [] }),
        });

      const mgr = activityEditorManager();
      mgr.init();

      const event = new CustomEvent("open-activity-editor", {
        detail: { activityId: 1 },
      });

      window.dispatchEvent(event);

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 10));

      expect(mgr.visible).toBe(true);
    });

    test("should open editor for creation when event is dispatched", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ events: [] }),
      });

      const mgr = activityEditorManager();
      mgr.init();

      const event = new CustomEvent("open-activity-editor", {
        detail: { create: true },
      });

      window.dispatchEvent(event);

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 10));

      expect(mgr.visible).toBe(true);
      expect(mgr.editingActivity).toBe(false);
    });
  });
});
