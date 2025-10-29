// Tests para manejo de public_slug en activity_editor
describe("activityEditorManager - public_slug", () => {
  let mockFetch, activityEditorManager;

  beforeEach(() => {
    jest.resetModules();
    mockFetch = jest.fn();
    global.fetch = mockFetch;
    global.safeFetch = mockFetch;
    global.showToast = jest.fn();
    activityEditorManager = require("../activity_editor.js");
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test("default currentActivity contains public_slug", () => {
    const mgr = activityEditorManager();
    expect(mgr.currentActivity).toHaveProperty("public_slug");
    expect(mgr.currentActivity.public_slug).toBe("");
  });

  test("generateSlugFromName calls API and sets public_slug", async () => {
    const mgr = activityEditorManager();
    mgr.currentActivity.name = "Actividad de Prueba";
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ slug: "actividad-de-prueba" }),
    });

    await mgr.generateSlugFromName();

    expect(mockFetch).toHaveBeenCalledWith("/api/activities/generate-slug", {
      method: "POST",
      body: JSON.stringify({ name: "Actividad de Prueba" }),
    });
    expect(mgr.currentActivity.public_slug).toBe("actividad-de-prueba");
  });
});
