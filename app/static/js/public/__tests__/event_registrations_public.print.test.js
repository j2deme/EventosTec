/** Tests del botón "Imprimir" (lista imprimible) de la vista de Jefes */

/** @jest-environment jsdom */
jest.resetModules();

// El módulo no exporta por CommonJS: expone la factory en window
require("../../public/event_registrations_public");

describe("eventRegistrationsPublic.printAttendanceListForActivity", () => {
  let mgr, openSpy;

  beforeEach(() => {
    jest.resetModules();
    require("../../public/event_registrations_public");
    mgr = window.eventRegistrationsPublic();

    // showToast disponible para no caer en alert() de jsdom
    window.showToast = jest.fn();
    openSpy = jest.fn(() => ({}));
    window.open = openSpy;
  });

  afterEach(() => {
    delete window.showToast;
    try {
      delete window.open;
    } catch (e) {
      /* noop */
    }
  });

  test("abre la lista imprimible en pestaña nueva usando el public_slug", () => {
    mgr.printAttendanceListForActivity({
      id: 42,
      public_slug: "taller-x",
      name: "Taller X",
    });

    expect(openSpy).toHaveBeenCalledTimes(1);
    expect(openSpy.mock.calls[0][0]).toBe("/public/attendance-list/taller-x");
    expect(openSpy.mock.calls[0][1]).toBe("_blank");
  });

  test("prefiere el public_slug (y lo codifica en la URL)", () => {
    mgr.printAttendanceListForActivity({
      id: 42,
      public_slug: "taller 2026",
    });

    expect(openSpy.mock.calls[0][0]).toBe(
      "/public/attendance-list/taller%202026",
    );
  });

  test("con solo id numérico (sin public_slug) no abre nada y avisa", () => {
    mgr.printAttendanceListForActivity({ id: 42, name: "Solo id" });

    expect(openSpy).not.toHaveBeenCalled();
    expect(window.showToast).toHaveBeenCalled();
  });

  test("si el navegador bloquea la pestaña, navega en la misma", () => {
    const origLocation = window.location;
    Object.defineProperty(window, "location", {
      value: { href: "about:blank" },
      writable: true,
      configurable: true,
    });
    openSpy.mockReturnValue(null);

    try {
      mgr.printAttendanceListForActivity({ id: 7, public_slug: "curso-7" });
      expect(window.location.href).toBe("/public/attendance-list/curso-7");
    } finally {
      Object.defineProperty(window, "location", {
        value: origLocation,
        writable: true,
        configurable: true,
      });
    }
  });

  test("sin identificador de actividad no abre nada y avisa", () => {
    mgr.printAttendanceListForActivity({ name: "Sin id" });

    expect(openSpy).not.toHaveBeenCalled();
    expect(window.showToast).toHaveBeenCalled();
  });

  test("sin actividad no hace nada", () => {
    mgr.printAttendanceListForActivity(null);

    expect(openSpy).not.toHaveBeenCalled();
    expect(window.showToast).not.toHaveBeenCalled();
  });
});
