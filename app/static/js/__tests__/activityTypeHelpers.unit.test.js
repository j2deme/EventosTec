// Unit tests for helpers/activityTypeHelpers.js
// Paleta/iconos compartidos por la vista de admin (calendario) y la del
// estudiante.

/** @jest-environment jsdom */
describe("activityTypeHelpers (commonjs + browser exposure)", () => {
  beforeEach(() => {
    jest.resetModules();
    if (typeof window !== "undefined") delete window.activityTypeHelpers;
  });

  test("module exports the helper and exposes window.activityTypeHelpers", () => {
    const at = require("../helpers/activityTypeHelpers");
    expect(at.__initialized).toBe(true);
    expect(window.activityTypeHelpers).toBe(at);
    expect(typeof at.color).toBe("function");
    expect(typeof at.durationBetween).toBe("function");
  });

  test("module is idempotent when window.activityTypeHelpers already exists", () => {
    const sentinel = { __initialized: true, color: () => "sentinel" };
    window.activityTypeHelpers = sentinel;

    const at = require("../helpers/activityTypeHelpers");
    expect(at).toBe(sentinel);
  });
});

describe("activityTypeHelpers (paleta canónica por tipo)", () => {
  let at;

  beforeEach(() => {
    jest.resetModules();
    if (typeof window !== "undefined") delete window.activityTypeHelpers;
    at = require("../helpers/activityTypeHelpers");
  });

  // Decisión de producto: Magistral=indigo (color main), Conferencia=yellow,
  // Taller=green, Curso=blue, Otro=gray.
  test("expone exactamente los 4 tipos del enum", () => {
    expect(at.keys().sort()).toEqual([
      "Conferencia",
      "Curso",
      "Magistral",
      "Taller",
    ]);
    expect(at.has("Taller")).toBe(true);
    expect(at.has("Otro")).toBe(false);
  });

  test("cada tipo tiene borde fuerte, círculo suave, chip e icono", () => {
    expect(at.border("Magistral")).toBe("border-indigo-600");
    expect(at.soft("Magistral")).toBe("bg-indigo-100 text-indigo-700");
    expect(at.icon("Magistral")).toBe("ti-school");

    expect(at.border("Conferencia")).toBe("border-yellow-600");
    expect(at.soft("Conferencia")).toBe("bg-yellow-100 text-yellow-700");
    expect(at.icon("Conferencia")).toBe("ti-presentation");

    expect(at.border("Taller")).toBe("border-green-600");
    expect(at.soft("Taller")).toBe("bg-green-100 text-green-700");
    expect(at.icon("Taller")).toBe("ti-tools");

    expect(at.border("Curso")).toBe("border-blue-600");
    expect(at.soft("Curso")).toBe("bg-blue-100 text-blue-700");
    expect(at.icon("Curso")).toBe("ti-device-laptop");
  });

  test("chip incluye borde + superficie + texto del mismo tono", () => {
    expect(at.color("Taller")).toBe(
      "border-green-600 bg-green-50 text-green-900",
    );
    expect(at.color("Curso")).toContain("bg-blue-50");
    expect(at.color("Magistral")).toContain("text-indigo-900");
  });

  test("tipos desconocidos o nulos caen en 'Otro' (gray)", () => {
    expect(at.border("Otro")).toBe("border-gray-400");
    expect(at.soft(undefined)).toBe("bg-gray-100 text-gray-600");
    expect(at.color(null)).toBe("border-gray-400 bg-gray-50 text-gray-800");
    expect(at.icon("Foo")).toBe("ti-tag");
    expect(at.label("Foo")).toBe("Otro");
  });

  test("tag (píldora de tipo en tablas) usa la misma paleta", () => {
    expect(at.tag("Magistral")).toBe("bg-indigo-100 text-indigo-800");
    expect(at.tag("Conferencia")).toBe("bg-yellow-100 text-yellow-800");
    expect(at.tag("Taller")).toBe("bg-green-100 text-green-800");
    expect(at.tag("Curso")).toBe("bg-blue-100 text-blue-800");
    expect(at.tag("Otro")).toBe("bg-gray-100 text-gray-800");
    expect(at.tag(null)).toBe("bg-gray-100 text-gray-800");
  });

  test("iconFull combina `ti` + icono + color del tipo", () => {
    expect(at.iconFull("Magistral")).toBe("ti ti-school text-indigo-600");
    expect(at.iconFull("Conferencia")).toBe(
      "ti ti-presentation text-yellow-600",
    );
    expect(at.iconFull("Taller")).toBe("ti ti-tools text-green-600");
    expect(at.iconFull("Curso")).toBe("ti ti-device-laptop text-blue-600");
    expect(at.iconFull("Otro")).toBe("ti ti-tag text-gray-600");
    expect(at.iconFull(undefined)).toBe("ti ti-tag text-gray-600");
  });

  test("durationBetween devuelve la duración por sesión", () => {
    expect(at.durationBetween("09:00", "13:00")).toBe("4 h");
    expect(at.durationBetween("09:00", "10:30")).toBe("1 h 30 min");
    expect(at.durationBetween("09:00", "09:45")).toBe("45 min");
    expect(at.durationBetween("09:00:00", "11:00:00")).toBe("2 h");
  });

  test("durationBetween acepta datetimes locales y cruces de medianoche", () => {
    expect(
      at.durationBetween("2026-10-08T08:00:00", "2026-10-08T13:00:00"),
    ).toBe("5 h");
    // Sesión que termina al día siguiente
    expect(at.durationBetween("19:00", "00:00")).toBe("5 h");
  });

  test("durationBetween devuelve '' si falta datos o es inválido", () => {
    expect(at.durationBetween(null, "13:00")).toBe("");
    expect(at.durationBetween("09:00", undefined)).toBe("");
    expect(at.durationBetween("", "")).toBe("");
    expect(at.durationBetween("no-hora", "13:00")).toBe("");
    expect(at.durationBetween("09:00", "09:00")).toBe(""); // misma hora = 0
    // Sin cruce de medianoche la resta negativa se compensa (+24 h)
    expect(at.durationBetween("13:00", "09:00")).toBe("20 h");
  });
});
