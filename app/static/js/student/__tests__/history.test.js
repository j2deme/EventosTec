/** Tests for student history component */

/** @jest-environment jsdom */
jest.resetModules();

// Mock localStorage before requiring the module
global.localStorage = {
  getItem: jest.fn((key) => {
    if (key === "authToken") {
      // Return a valid JWT-like token with sub claim
      const payload = { sub: 123, exp: Math.floor(Date.now() / 1000) + 3600 };
      const encodedPayload = Buffer.from(JSON.stringify(payload)).toString(
        "base64",
      );
      return `header.${encodedPayload}.signature`;
    }
    return null;
  }),
  setItem: jest.fn(),
  removeItem: jest.fn(),
};

if (typeof window === "undefined") global.window = {};
window.localStorage = global.localStorage;

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
    const studentId = mgr.getCurrentStudentId();
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
