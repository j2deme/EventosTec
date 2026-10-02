// Unit tests for helpers/dateHelpers.js

describe("dateHelpers (commonjs + browser exposure)", () => {
  beforeEach(() => {
    // Ensure fresh module load and clean window state
    jest.resetModules();
    if (typeof window !== "undefined") {
      delete window.dateHelpers;
    }
  });

  test("exports expected functions", () => {
    const dh = require("../helpers/dateHelpers.js");
    expect(dh).toBeDefined();
    expect(typeof dh.formatDateTime).toBe("function");
    expect(typeof dh.formatTime).toBe("function");
    expect(typeof dh.formatOnlyDate).toBe("function");
    expect(typeof dh.formatDateTimeForInput).toBe("function");
    expect(typeof dh.formatDateShort).toBe("function");
    expect(typeof dh.formatDateTimeShort).toBe("function");
    expect(typeof dh.dateKey).toBe("function");
  });

  test("formatDateTime returns localized human string and not raw ISO", () => {
    const dh = require("../helpers/dateHelpers.js");
    const iso = "2025-09-19T08:00:00Z";
    const out = dh.formatDateTime(iso);
    expect(typeof out).toBe("string");
    // should include year and not be the raw ISO string
    expect(out).toContain("2025");
    expect(out).not.toMatch(/2025-09-19T08:00:00Z/);
    // should contain a month name (letters) in the output
    expect(out).toMatch(/[a-záéíóúñ]+/i);
  });

  test("formatTime returns a short time string (contains colon)", () => {
    const dh = require("../helpers/dateHelpers.js");
    const out = dh.formatTime("2025-09-19T17:30:00Z");
    expect(typeof out).toBe("string");
    expect(out).toMatch(/\d{1,2}:\d{2}/);
  });

  test("module is idempotent when window.dateHelpers already exists", () => {
    // Simulate browser pre-existing helper
    if (typeof window === "undefined") global.window = {};
    const sentinel = { __initialized: true, formatDateTime: () => "SENTINEL" };
    window.dateHelpers = sentinel;
    jest.resetModules();
    const dh = require("../helpers/dateHelpers.js");
    // The module should export the window.dateHelpers reference when present
    expect(dh).toBe(window.dateHelpers);
    expect(dh.formatDateTime()).toBe("SENTINEL");
  });
});

describe("dateHelpers (fechas puras YYYY-MM-DD → parseo LOCAL)", () => {
  beforeEach(() => {
    jest.resetModules();
    if (typeof window !== "undefined") {
      delete window.dateHelpers;
    }
  });

  // Regresión: new Date("2026-10-08") es medianoche UTC; en zonas al oeste
  // de UTC (América) se formateaba como "7 de octubre" — el encabezado del
  // día en la vista de estudiantes mostraba siempre el día anterior.

  test("formatOnlyDate no retrocede al día anterior", () => {
    const dh = require("../helpers/dateHelpers.js");
    const esperado = new Date(2026, 9, 8).toLocaleDateString("es-MX", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
    expect(dh.formatOnlyDate("2026-10-08")).toBe(esperado);
  });

  test("formatDateTimeForInput fecha pura → medianoche local", () => {
    const dh = require("../helpers/dateHelpers.js");
    expect(dh.formatDateTimeForInput("2026-10-08")).toBe("2026-10-08T00:00");
  });

  test("formatDateTimeForInput conserva datetime con hora sin cambios", () => {
    const dh = require("../helpers/dateHelpers.js");
    expect(dh.formatDateTimeForInput("2026-10-08T09:00:00")).toBe(
      "2026-10-08T09:00",
    );
  });

  test("formatDate fecha pura contiene el mismo día", () => {
    const dh = require("../helpers/dateHelpers.js");
    expect(dh.formatDate("2026-10-08")).toContain("8");
  });
});

describe("dateHelpers (formato canónico: es-MX, 24 h, sin meridiano)", () => {
  beforeEach(() => {
    jest.resetModules();
    if (typeof window !== "undefined") {
      delete window.dateHelpers;
    }
  });

  // Decisión de producto: toda la plataforma muestra la hora en 24 h
  // ("09:00") con locale es-MX. Regresión: antes el helper canónico
  // producía "9:00 a. m." (hour12) y otros componentes "9:00 AM"/"3:00 PM".

  test("formatTime → HH:mm 24 h sin a. m./p. m.", () => {
    const dh = require("../helpers/dateHelpers.js");
    // naive local → hora local, independiente de la TZ del runner
    const out = dh.formatTime("2026-10-08T09:05:00");
    expect(out).toBe("09:05");
    expect(out).not.toMatch(/a\. m\.|p\. m\.|AM|PM/i);
  });

  test("formatDateTime → fecha larga con hora 24 h", () => {
    const dh = require("../helpers/dateHelpers.js");
    const out = dh.formatDateTime("2026-10-08T09:05:00");
    expect(out).toContain("2026");
    expect(out).toMatch(/09:05/);
    expect(out).not.toMatch(/a\. m\.|p\. m\./i);
  });

  test("formatShortDate → DD/MM/YYYY, HH:mm 24 h", () => {
    const dh = require("../helpers/dateHelpers.js");
    const out = dh.formatShortDate("2026-10-08T09:05:00");
    expect(out).toMatch(/\d{2}\/\d{2}\/\d{4}/);
    expect(out).toMatch(/\d{2}:\d{2}/);
    expect(out).not.toMatch(/a\. m\.|p\. m\./i);
  });

  test("formatDateShort → '8 oct 2026' y formatDateTimeShort con hora 24 h", () => {
    const dh = require("../helpers/dateHelpers.js");
    const f = dh.formatDateShort("2026-10-08");
    expect(f).toMatch(/8/);
    expect(f).toMatch(/oct/i);
    expect(f).toMatch(/2026/);

    const ft = dh.formatDateTimeShort("2026-10-08T09:05:00");
    expect(ft).toMatch(/oct/i);
    expect(ft).toMatch(/09:05/);
    expect(ft).not.toMatch(/a\. m\.|p\. m\./i);
  });

  test("dateKey → clave local YYYY-MM-DD", () => {
    const dh = require("../helpers/dateHelpers.js");
    expect(dh.dateKey("2026-10-08")).toBe("2026-10-08");
    expect(dh.dateKey("2026-10-08T23:30:00")).toBe("2026-10-08");
    expect(dh.dateKey(new Date(2026, 9, 8, 23, 59))).toBe("2026-10-08");
    expect(dh.dateKey("")).toBe("");
    expect(dh.dateKey(null)).toBe("");
    expect(dh.dateKey("no-es-fecha")).toBe("");
  });

  test("dateKey no se desplaza con fechas puras (regresión UTC)", () => {
    const dh = require("../helpers/dateHelpers.js");
    // new Date("2026-10-08") = medianoche UTC → en América daba "2026-10-07"
    expect(dh.dateKey("2026-10-08")).toBe("2026-10-08");
  });
});
