/** Tests for student history component */

/** @jest-environment jsdom */
jest.resetModules();

const studentHistoryManager = require("../history");

describe("studentHistoryManager", () => {
  let mgr;
  let fetchMock;

  beforeEach(() => {
    window.showToast = jest.fn();
    window.getAuthHeaders = jest.fn(() => ({
      Authorization: "Bearer test-token",
      "Content-Type": "application/json",
    }));

    // Mock fetch
    fetchMock = jest.fn();
    global.fetch = fetchMock;

    mgr = studentHistoryManager();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test("initializes with correct default state", () => {
    expect(mgr.eventsHours).toEqual([]);
    expect(mgr.loading).toBe(false);
    expect(mgr.showEventDetailModal).toBe(false);
  });

  test("getCurrentStudentId decodes JWT token", () => {
    // Usar el localStorage real de jsdom: el asignador de window.localStorage
    // no reemplaza al storage nativo y el mock quedaba sin efecto.
    const payload = { sub: 123, exp: Math.floor(Date.now() / 1000) + 3600 };
    const encodedPayload = Buffer.from(JSON.stringify(payload)).toString(
      "base64",
    );
    localStorage.setItem("authToken", `header.${encodedPayload}.signature`);

    const studentId = mgr.getCurrentStudentId();

    localStorage.removeItem("authToken");
    expect(studentId).toBe(123);
  });

  test("getStatusBadgeClass returns correct classes", () => {
    expect(mgr.getStatusBadgeClass("Asistió")).toContain("green");
    expect(mgr.getStatusBadgeClass("Confirmado")).toContain("blue");
    expect(mgr.getStatusBadgeClass("Registrado")).toContain("yellow");
    expect(mgr.getStatusBadgeClass("Ausente")).toContain("red");
    expect(mgr.getStatusBadgeClass("Cancelado")).toContain("gray");
  });
});
