/** Tests for the student activities-by-event view (presentation helpers) */

/** @jest-environment jsdom */
jest.resetModules();

// El módulo no exporta por CommonJS: expone la factory en window
require("../event_activities");
// Helper compartido con la vista de admin (paleta/iconos por tipo)
require("../../helpers/activityTypeHelpers");

describe("studentEventActivitiesManager (presentación)", () => {
  let mgr;

  beforeEach(() => {
    jest.resetModules();
    mgr = window.studentEventActivitiesManager();
    mgr.studentRegistrations = [];
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  // Helpers para simular la geometría del scroll (jsdom no maqueta)
  const rect = (top, height = 100) => ({
    top,
    bottom: top + height,
    left: 0,
    right: 0,
    width: 0,
    height,
  });

  function fakeBar(bottom) {
    const el = document.createElement("div");
    el.setAttribute("data-day-index", "");
    el.getBoundingClientRect = () => rect(0, bottom);
    document.body.appendChild(el);
    return el;
  }

  function fakeSection(date, top) {
    const el = document.createElement("div");
    el.id = "dia-" + date;
    el.getBoundingClientRect = () => rect(top);
    document.body.appendChild(el);
    return el;
  }

  // --- Tipos: mismo lenguaje visual que el admin ---

  test("typeBorder usa la paleta canónica compartida", () => {
    expect(window.activityTypeHelpers).toBeDefined();
    expect(mgr.typeBorder("Magistral")).toBe("border-indigo-600");
    expect(mgr.typeBorder("Conferencia")).toBe("border-yellow-600");
    expect(mgr.typeBorder("Taller")).toBe("border-green-600");
    expect(mgr.typeBorder("Curso")).toBe("border-blue-600");
    expect(mgr.typeBorder(undefined)).toBe("border-gray-400");
  });

  test("typeSoft/typeIcon exponen el círculo y el icono del tipo", () => {
    expect(mgr.typeSoft("Taller")).toBe("bg-green-100 text-green-700");
    expect(mgr.typeIcon("Taller")).toBe("ti-tools");
    expect(mgr.typeIcon("Conferencia")).toBe("ti-presentation");
    expect(mgr.typeIcon("Desconocido")).toBe("ti-tag");
  });

  test("degrada a neutro si el helper no cargó", () => {
    const original = window.activityTypeHelpers;
    try {
      delete window.activityTypeHelpers;
      expect(mgr.typeBorder("Taller")).toBe("border-gray-400");
      expect(mgr.typeIcon("Taller")).toBe("ti-tag");
    } finally {
      window.activityTypeHelpers = original;
    }
  });

  // --- Disponibilidad ---

  test("availabilityCode distingue disponible / lleno / registrado", () => {
    expect(
      mgr.availabilityCode({ id: 1, max_capacity: 40, current_capacity: 5 }),
    ).toBe("available");
    expect(mgr.availabilityCode({ id: 2, max_capacity: null })).toBe(
      "available",
    );
    expect(
      mgr.availabilityCode({ id: 3, max_capacity: 40, current_capacity: 40 }),
    ).toBe("full");
    expect(mgr.availabilityCode(null)).toBe("available");

    // Registrado gana sobre "lleno"
    mgr.studentRegistrations = [4];
    expect(
      mgr.availabilityCode({ id: 4, max_capacity: 40, current_capacity: 40 }),
    ).toBe("registered");
  });

  test("availabilityLabel muestra el estado en español", () => {
    expect(
      mgr.availabilityLabel({ id: 1, max_capacity: 40, current_capacity: 1 }),
    ).toBe("Disponible");
    expect(
      mgr.availabilityLabel({ id: 2, max_capacity: 10, current_capacity: 10 }),
    ).toBe("Cupo lleno");
    expect(
      mgr.availabilityLabel({ id: 3, max_capacity: 40, current_capacity: 1 }),
    ).toBe("Disponible");
    mgr.studentRegistrations = [3];
    expect(
      mgr.availabilityLabel({ id: 3, max_capacity: 40, current_capacity: 1 }),
    ).toBe("Registrado");
  });

  // --- Duración por sesión ---

  test("sessionDuration calcula la duración de la sesión, no el total", () => {
    expect(
      mgr.sessionDuration({
        start_datetime: "2026-10-08T08:00:00",
        end_datetime: "2026-10-08T13:00:00",
      }),
    ).toBe("5 h");
    expect(
      mgr.sessionDuration({
        start_datetime: "2026-10-08T09:00:00",
        end_datetime: "2026-10-08T10:30:00",
      }),
    ).toBe("1 h 30 min");
    expect(mgr.sessionDuration(null)).toBe("");
    // Sin horario: fallback al total de la actividad
    expect(mgr.sessionDuration({ duration_hours: 14 })).toBe("14 h");
  });

  // --- Índice de días sticky ---

  test("dayLabel no corrije el día por el parseo UTC", () => {
    const label = mgr.dayLabel("2026-10-06");
    expect(label).toContain("6");
    expect(mgr.dayLabel("no-date")).toBe("no-date");
    expect(mgr.dayLabel("")).toBe("");
    expect(mgr.dayLabel(null)).toBe("");
  });

  test("scrollToDay no falla si la sección del día no existe", () => {
    expect(() => mgr.scrollToDay("2026-10-07")).not.toThrow();
  });

  // --- Día activo en el índice sticky (scroll spy) ---

  test("scrollToDay marca el día de inmediato (feedback sin esperar al scroll)", () => {
    mgr.scrollToDay("2026-10-08");
    expect(mgr.activeDay).toBe("2026-10-08");
  });

  test("updateActiveDay marca la sección que ya cruzó la barra sticky", () => {
    mgr.activitiesByDay = [
      { date: "2026-10-07", activities: [] },
      { date: "2026-10-08", activities: [] },
      { date: "2026-10-09", activities: [] },
    ];
    fakeBar(40); // borde inferior en y=40 → línea de referencia 41
    fakeSection("2026-10-07", -200); // ya pasó
    fakeSection("2026-10-08", 20); // recién cubierto por la barra → activo
    fakeSection("2026-10-09", 400); // aún no llega

    mgr.updateActiveDay();
    expect(mgr.activeDay).toBe("2026-10-08");

    // Al entrar la última sección, ella toma el relevo
    document.getElementById("dia-2026-10-09").getBoundingClientRect = () =>
      rect(30);
    mgr.updateActiveDay();
    expect(mgr.activeDay).toBe("2026-10-09");
  });

  test("updateActiveDay limpia activeDay si no hay días", () => {
    mgr.activeDay = "2026-10-07";
    mgr.activitiesByDay = [];
    mgr.updateActiveDay();
    expect(mgr.activeDay).toBeNull();
  });

  test("activeDayLine cae a un offset fijo si la barra no es visible", () => {
    expect(mgr.activeDayLine()).toBe(96);

    const hidden = document.createElement("div");
    hidden.setAttribute("data-day-index", "");
    hidden.getBoundingClientRect = () => rect(0, 0); // bottom = 0 → oculta
    document.body.appendChild(hidden);
    expect(mgr.activeDayLine()).toBe(96);
  });

  test("initDaySpy/destroyDaySpy registran y quitan los listeners", () => {
    const add = jest.spyOn(window, "addEventListener");
    const remove = jest.spyOn(window, "removeEventListener");
    try {
      mgr.initDaySpy();
      expect(add.mock.calls.map((c) => c[0])).toEqual(
        expect.arrayContaining(["scroll", "resize", "beforeunload"]),
      );
      expect(mgr._spyHandler).toBeTruthy();

      // Idempotente: no duplica listeners
      const total = add.mock.calls.length;
      mgr.initDaySpy();
      expect(add.mock.calls.length).toBe(total);

      const handler = mgr._spyHandler;
      mgr.destroyDaySpy();
      expect(remove.mock.calls.map((c) => [c[0], c[1]])).toEqual(
        expect.arrayContaining([
          ["scroll", handler],
          ["resize", handler],
        ]),
      );
      expect(mgr._spyHandler).toBeNull();

      // Doble destrucción no revienta
      expect(() => mgr.destroyDaySpy()).not.toThrow();
    } finally {
      add.mockRestore();
      remove.mockRestore();
    }
  });
});
