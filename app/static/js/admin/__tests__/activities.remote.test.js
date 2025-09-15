// Tests for activities remote operations (fetch) - mocks fetch and localStorage
require("../../app.js");
const activitiesManager = require("../activities.js");

describe("activitiesManager remote operations", () => {
  let mgr;
  beforeEach(() => {
    // Mock localStorage and showToast
    global.localStorage = {
      getItem: jest.fn(() => "FAKE_TOKEN"),
      setItem: jest.fn(),
      removeItem: jest.fn(),
    };
    global.showToast = jest.fn();
    mgr = activitiesManager();
    jest.restoreAllMocks();
  });

  test("getRelatedActivities throws when fetch returns non-ok", async () => {
    global.fetch = jest.fn(() => Promise.resolve({ ok: false }));
    await expect(mgr.getRelatedActivities(123)).rejects.toThrow(
      "Error al obtener actividades relacionadas"
    );
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/activities/123/related",
      expect.any(Object)
    );
  });

  test("linkActivity calls fetch and shows success toast on ok", async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    );
    await expect(mgr.linkActivity(10, 20)).resolves.toBeUndefined();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/activities/10/related",
      expect.objectContaining({ method: "POST" })
    );
    expect(global.showToast).toHaveBeenCalledWith(
      "Actividades enlazadas exitosamente",
      "success"
    );
  });

  test("unlinkActivity calls fetch and shows success toast on ok", async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    );
    await expect(mgr.unlinkActivity(11, 21)).resolves.toBeUndefined();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/activities/11/related/21",
      expect.objectContaining({ method: "DELETE" })
    );
    expect(global.showToast).toHaveBeenCalledWith(
      "Actividades desenlazadas exitosamente",
      "success"
    );
  });
});
