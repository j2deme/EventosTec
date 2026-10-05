/** Tests for the public "Jefes de Carrera" view (presentación por tipo) */

/** @jest-environment jsdom */
jest.resetModules();

// El módulo no exporta por CommonJS: expone la factory en window
require("../../public/event_registrations_public");
// Fuente única de paleta/iconos (en producción la inyecta base.html)
require("../../helpers/activityTypeHelpers");

describe("eventRegistrationsPublic (presentación por tipo)", () => {
  let mgr;

  beforeEach(() => {
    mgr = window.eventRegistrationsPublic();
  });

  test("typeIconFull expone `ti` + icono + color canónicos", () => {
    expect(mgr.typeIconFull("Magistral")).toBe("ti ti-school text-indigo-600");
    expect(mgr.typeIconFull("Conferencia")).toBe(
      "ti ti-presentation text-yellow-600",
    );
    expect(mgr.typeIconFull("Taller")).toBe("ti ti-tools text-green-600");
    expect(mgr.typeIconFull("Curso")).toBe("ti ti-device-laptop text-blue-600");
    expect(mgr.typeIconFull("Otro")).toBe("ti ti-tag text-gray-600");
  });

  test("typeTag usa la píldora canónica de la paleta compartida", () => {
    expect(mgr.typeTag("Magistral")).toBe("bg-indigo-100 text-indigo-800");
    expect(mgr.typeTag("Conferencia")).toBe("bg-yellow-100 text-yellow-800");
    expect(mgr.typeTag("Taller")).toBe("bg-green-100 text-green-800");
    expect(mgr.typeTag("Curso")).toBe("bg-blue-100 text-blue-800");
    expect(mgr.typeTag(null)).toBe("bg-gray-100 text-gray-800");
  });

  test("degrada a neutro si el helper no cargó", () => {
    const original = window.activityTypeHelpers;
    try {
      delete window.activityTypeHelpers;
      expect(mgr.typeIconFull("Taller")).toBe("ti ti-tag text-gray-600");
      expect(mgr.typeTag("Taller")).toBe("bg-gray-100 text-gray-800");
    } finally {
      if (original) window.activityTypeHelpers = original;
    }
  });
});
