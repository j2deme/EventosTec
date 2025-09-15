/**
 * Tests for global date helpers exposed by app/static/js/app.js
 */

// Require the app script so it exposes window.format* helpers
require("../app.js");

describe("Global date helpers (app.js)", () => {
  test("window.formatDateTimeForInput returns YYYY-MM-DDTHH:MM pattern for ISO input", () => {
    const dt = "2025-09-01T10:30:00Z";
    const result = window.formatDateTimeForInput(dt);
    expect(result).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/);
  });

  test("formatDateTimeForInput returns empty string for falsy input", () => {
    expect(window.formatDateTimeForInput(null)).toBe("");
    expect(window.formatDateTimeForInput(undefined)).toBe("");
    expect(window.formatDateTimeForInput("")).toBe("");
  });

  test('formatDate returns "Sin fecha" for falsy and returns string for valid date', () => {
    expect(window.formatDate(null)).toBe("Sin fecha");
    const out = window.formatDate("2025-09-01T10:30:00Z");
    expect(typeof out).toBe("string");
    expect(out.length).toBeGreaterThan(0);
  });

  test('formatOnlyDate returns non-empty for valid date and "Sin fecha" for falsy', () => {
    expect(window.formatOnlyDate(null)).toBe("Sin fecha");
    const out = window.formatOnlyDate("2025-09-01T10:30:00Z");
    expect(typeof out).toBe("string");
    expect(out.length).toBeGreaterThan(0);
  });

  test("formatShortDate returns expected pattern for valid date", () => {
    const out = window.formatShortDate("2025-09-01T10:30:00Z");
    // expected like DD/MM/YYYY HH:MM or similar
    expect(out).toMatch(/\d{2}\/\d{2}\/\d{4}/);
  });

  test('formatDateTime returns "Sin fecha" for falsy and non-empty for valid', () => {
    expect(window.formatDateTime(null)).toBe("Sin fecha");
    const out = window.formatDateTime("2025-09-01T10:30:00Z");
    expect(typeof out).toBe("string");
    expect(out.length).toBeGreaterThan(0);
  });
});
