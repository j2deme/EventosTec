/** Tests de claves de fecha en series multidía (vistas de estudiantes) */
/** @jest-environment jsdom */
jest.resetModules();

require("../event_activities");

describe("day_in_series (serie multidía) sin off-by-one", () => {
  let activitiesMgr;

  beforeEach(() => {
    window.showToast = jest.fn();
    window.getAuthHeaders = jest.fn(() => ({
      Authorization: "Bearer test-token",
      "Content-Type": "application/json",
    }));
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
    );

    activitiesMgr = window.studentEventActivitiesManager();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  // Regresión: las claves "YYYY-MM-DD" se parseaban como medianoche UTC y en
  // zonas al oeste de UTC el primer día de la serie calculaba 0 (y los
  // siguientes quedaban 1, 2... en vez de 1, 2, 3), desfasando el badge
  // "Sesión n/m" y el botón de preregistro multidía.
  // (El duplicado equivalente en studentDashboard se eliminó: no tenía
  // llamadores — los parciales de estudiante usan su propio x-data.)

  test("event_activities: 1..n para claves de fecha pura", () => {
    const start = "2026-10-08T09:00:00";
    const end = "2026-10-10T16:00:00";
    expect(activitiesMgr.getDayInSeries(start, end, "2026-10-08")).toBe(1);
    expect(activitiesMgr.getDayInSeries(start, end, "2026-10-09")).toBe(2);
    expect(activitiesMgr.getDayInSeries(start, end, "2026-10-10")).toBe(3);
  });

  test("event_activities: getTotalDays cuenta 3 días naturales", () => {
    expect(
      activitiesMgr.getTotalDays("2026-10-08T09:00:00", "2026-10-10T16:00:00"),
    ).toBe(3);
  });
});
