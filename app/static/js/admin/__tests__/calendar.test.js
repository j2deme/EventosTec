/** Tests for admin calendar component */

/** @jest-environment jsdom */
jest.resetModules();

const calendarAdmin = require("../calendar");
// Helper compartido con la vista del estudiante (paleta/iconos por tipo)
const activityTypeHelpers = require("../../helpers/activityTypeHelpers");

describe("calendarAdmin", () => {
  let mgr;
  let fetchMock;

  beforeEach(() => {
    // Setup global mocks
    global.localStorage = {
      getItem: jest.fn(),
      setItem: jest.fn(),
      removeItem: jest.fn(),
    };

    if (typeof window === "undefined") global.window = {};
    window.localStorage = global.localStorage;
    window.showToast = jest.fn();
    window.getAuthHeaders = jest.fn(() => ({
      Authorization: "Bearer test-token",
      "Content-Type": "application/json",
    }));

    // Mock fetch
    fetchMock = jest.fn();
    global.fetch = fetchMock;

    mgr = calendarAdmin();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test("initializes with correct default state", () => {
    expect(mgr.loading).toBe(false);
    expect(mgr.errorMessage).toBe("");
    expect(mgr.events).toEqual([]);
    expect(mgr.selectedEventId).toBeNull();
    expect(mgr.calendar).toBeNull();
    expect(mgr.showDetail).toBe(false);
    expect(mgr.selectedActivity).toBeNull();
  });

  test("loadEvents selects first event and loads its calendar", async () => {
    const eventsPayload = {
      events: [
        { id: 7, name: "46° Aniversario" },
        { id: 1, name: "45° Aniversario" },
      ],
    };
    const calendarPayload = {
      event: { id: 7, name: "46° Aniversario" },
      days: ["2026-10-06"],
      activities: [],
      total_activities: 0,
    };

    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => eventsPayload })
      .mockResolvedValueOnce({ ok: true, json: async () => calendarPayload });

    await mgr.loadEvents();

    expect(mgr.events).toHaveLength(2);
    expect(mgr.selectedEventId).toBe("7");
    expect(mgr.calendar).toEqual(calendarPayload);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toContain("/api/events/");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/events/7/calendar");
    expect(mgr.loading).toBe(false);
  });

  test("loadEvents handles error response", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 500 });

    await mgr.loadEvents();

    expect(mgr.errorMessage).toBe("Error al cargar los eventos");
    expect(mgr.events).toEqual([]);
    expect(mgr.loading).toBe(false);
  });

  test("loadEvents with no events leaves calendar untouched", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ events: [] }),
    });

    await mgr.loadEvents();

    expect(mgr.events).toEqual([]);
    expect(mgr.calendar).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test("onEventChange loads selected event calendar", async () => {
    mgr.selectedEventId = "3";
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ event: { id: 3 }, days: [], activities: [] }),
    });

    await mgr.onEventChange();

    expect(fetchMock).toHaveBeenCalledWith("/api/events/3/calendar");
    expect(mgr.calendar).not.toBeNull();
  });

  test("onEventChange with no selection does nothing", async () => {
    mgr.selectedEventId = null;
    await mgr.onEventChange();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("loadCalendar handles error response", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 404 });

    await mgr.loadCalendar(9);

    expect(mgr.errorMessage).toBe("Error al cargar el calendario");
    expect(mgr.calendar).toBeNull();
  });

  test("loadCalendar handles fetch rejection", async () => {
    fetchMock.mockRejectedValueOnce(new Error("network down"));

    await mgr.loadCalendar(9);

    expect(mgr.errorMessage).toBe("network down");
    expect(mgr.loading).toBe(false);
  });

  // --- Helpers de vista ---

  describe("view helpers", () => {
    beforeEach(() => {
      mgr.calendar = {
        event: {
          id: 7,
          name: "Test",
          start_date: "2026-10-06",
          end_date: "2026-10-08",
        },
        days: ["2026-10-06", "2026-10-07", "2026-10-08"],
        activities: [
          {
            id: 1,
            day: "2026-10-07",
            starts_at: "13:00",
            ends_at: "14:00",
            name: "AutoCAD",
          },
          {
            id: 2,
            day: "2026-10-07",
            starts_at: "09:00",
            ends_at: "10:00",
            name: "Maniobras",
          },
          {
            id: 3,
            day: "2026-10-20",
            starts_at: "08:00",
            ends_at: "09:00",
            name: "Fuera de ventana",
          },
          {
            id: 4,
            day: null,
            starts_at: null,
            ends_at: null,
            name: "Sin fecha",
          },
        ],
        total_activities: 4,
      };
    });

    test("dayActivities filters by day and sorts by start time", () => {
      const result = mgr.dayActivities("2026-10-07");
      expect(result).toHaveLength(2);
      expect(result[0].name).toBe("Maniobras"); // 09:00 antes que 13:00
      expect(result[1].name).toBe("AutoCAD");
    });

    test("dayActivities returns empty array for day without activities", () => {
      expect(mgr.dayActivities("2026-10-06")).toEqual([]);
    });

    test("dayActivities returns empty array when no calendar", () => {
      mgr.calendar = null;
      expect(mgr.dayActivities("2026-10-07")).toEqual([]);
    });

    test("dayCount returns number of activities of a day", () => {
      expect(mgr.dayCount("2026-10-07")).toBe(2);
      expect(mgr.dayCount("2026-10-06")).toBe(0);
    });

    test("outsideActivities returns activities outside window or without date", () => {
      const result = mgr.outsideActivities();
      expect(result.map((a) => a.id)).toEqual([3, 4]);
    });

    test("outsideActivities returns empty array when no calendar", () => {
      mgr.calendar = null;
      expect(mgr.outsideActivities()).toEqual([]);
    });

    test("dayLabel does not shift day due to UTC parsing", () => {
      // Parseo local (no UTC): "2026-10-06" siempre etiqueta el día 6
      const expected = new Date(2026, 9, 6).toLocaleDateString("es-MX", {
        weekday: "short",
        day: "numeric",
        month: "short",
      });
      expect(mgr.dayLabel("2026-10-06")).toBe(expected);
      expect(mgr.dayLabel("2026-10-06")).toContain("6");
    });

    test("dayLabel falls back gracefully on invalid input", () => {
      expect(mgr.dayLabel("no-date")).toBe("no-date");
    });

    test("typeColor delega la paleta canónica al helper compartido", () => {
      // El helper compartido es el que calendar.js lee en tiempo de llamada
      expect(window.activityTypeHelpers).toBe(activityTypeHelpers);
      // Paleta decidida: Magistral=indigo (color main), Conferencia=yellow,
      // Taller=green, Curso=blue, Otro=gray.
      expect(mgr.typeColor("Magistral")).toContain("indigo");
      expect(mgr.typeColor("Conferencia")).toContain("yellow");
      expect(mgr.typeColor("Taller")).toContain("green");
      expect(mgr.typeColor("Curso")).toContain("blue");
      expect(mgr.typeColor("Otro")).toContain("gray");
      expect(mgr.typeColor(undefined)).toContain("gray");
    });

    test("typeSoft/typeIcon exponen el círculo y el icono del tipo", () => {
      expect(mgr.typeSoft("Taller")).toBe("bg-green-100 text-green-700");
      expect(mgr.typeIcon("Taller")).toBe("ti-tools");
      expect(mgr.typeIcon("Magistral")).toBe("ti-school");
      expect(mgr.typeIcon("Desconocido")).toBe("ti-tag");
    });

    test("typeColor degrada a neutro si el helper no cargó", () => {
      const original = window.activityTypeHelpers;
      try {
        delete window.activityTypeHelpers;
        expect(mgr.typeColor("Taller")).toBe(
          "border-gray-400 bg-gray-50 text-gray-800",
        );
        expect(mgr.typeIcon("Taller")).toBe("ti-tag");
      } finally {
        window.activityTypeHelpers = original;
      }
    });

    test("cupoLevel clasifica el cupo para colorear el chip", () => {
      expect(mgr.cupoLevel(null)).toBe("none");
      expect(mgr.cupoLevel({ max_capacity: null })).toBe("none");
      expect(mgr.cupoLevel({ max_capacity: 40, registered_count: 5 })).toBe(
        "ok",
      );
      expect(mgr.cupoLevel({ max_capacity: 40 })).toBe("ok");
      expect(mgr.cupoLevel({ max_capacity: 40, registered_count: 38 })).toBe(
        "high",
      );
      expect(mgr.cupoLevel({ max_capacity: 40, registered_count: 40 })).toBe(
        "full",
      );
      expect(mgr.cupoLevel({ max_capacity: 40, registered_count: 41 })).toBe(
        "full",
      );
    });

    test("sessionDuration calcula la duración POR SESIÓN", () => {
      expect(
        mgr.sessionDuration({ starts_at: "09:00", ends_at: "13:00" }),
      ).toBe("4 h");
      expect(
        mgr.sessionDuration({ starts_at: "09:00", ends_at: "10:30" }),
      ).toBe("1 h 30 min");
      // Cruce de medianoche
      expect(
        mgr.sessionDuration({ starts_at: "19:00", ends_at: "00:00" }),
      ).toBe("5 h");
      expect(mgr.sessionDuration(null)).toBe("");
      expect(mgr.sessionDuration({ starts_at: null, ends_at: "13:00" })).toBe(
        "",
      );
      // Sin horario de sesión se cae al total de la actividad
      expect(
        mgr.sessionDuration({
          starts_at: null,
          ends_at: null,
          duration_hours: 14,
        }),
      ).toBe("14 h");
    });

    test("scrollToDay no falla si la columna del día no existe", () => {
      expect(() => mgr.scrollToDay("2026-10-07")).not.toThrow();
    });

    test("cupoLabel shows registered/capacity only when capacity defined", () => {
      expect(mgr.cupoLabel({ max_capacity: 30, registered_count: 12 })).toBe(
        "12/30",
      );
      expect(mgr.cupoLabel({ max_capacity: null, registered_count: 5 })).toBe(
        "",
      );
      expect(mgr.cupoLabel({ max_capacity: 10 })).toBe("0/10");
      expect(mgr.cupoLabel(null)).toBe("");
    });

    test("gridStyle uses one column per day", () => {
      expect(mgr.gridStyle()).toContain("repeat(3,");
      mgr.calendar.days = ["2026-10-06"];
      expect(mgr.gridStyle()).toContain("repeat(1,");
      mgr.calendar = null;
      expect(mgr.gridStyle()).toContain("repeat(1,");
    });
  });

  test("openDetail and closeDetail toggle modal state", () => {
    const activity = { id: 5, name: "Rally" };
    mgr.openDetail(activity);
    expect(mgr.showDetail).toBe(true);
    expect(mgr.selectedActivity).toBe(activity);

    mgr.closeDetail();
    expect(mgr.showDetail).toBe(false);
    expect(mgr.selectedActivity).toBeNull();
  });

  // --- Selector de vista: rango de días (default) vs horario de un día ----
  describe("setView / onDayPillClick / isDayActive", () => {
    beforeEach(() => {
      mgr.calendar = {
        days: ["2026-10-07", "2026-10-08", "2026-10-09"],
        activities: [],
      };
    });

    test("arranca en la vista de rango sin día seleccionado", () => {
      expect(mgr.viewMode).toBe("range");
      expect(mgr.selectedDay).toBeNull();
    });

    test("setView('day') fija el primer día disponible", () => {
      mgr.setView("day");
      expect(mgr.viewMode).toBe("day");
      expect(mgr.selectedDay).toBe("2026-10-07");
    });

    test("setView('day', dia) respeta el día pedido", () => {
      mgr.setView("day", "2026-10-09");
      expect(mgr.selectedDay).toBe("2026-10-09");
    });

    test("setView('day') prefiere la columna que se veía en rango", () => {
      mgr.activeDay = "2026-10-08";
      mgr.setView("day");
      expect(mgr.selectedDay).toBe("2026-10-08");
    });

    test("setView('day') ignora un día que ya no existe", () => {
      mgr.selectedDay = "2026-11-30";
      mgr.setView("day");
      expect(mgr.selectedDay).toBe("2026-10-07");
    });

    test("setView('range') vuelve al rango conservando el día", () => {
      mgr.setView("day", "2026-10-09");
      mgr.setView("range");
      expect(mgr.viewMode).toBe("range");
      expect(mgr.selectedDay).toBe("2026-10-09");
    });

    test("setView sin calendario no revienta", () => {
      mgr.calendar = null;
      expect(() => mgr.setView("day")).not.toThrow();
      expect(mgr.viewMode).toBe("day");
      expect(mgr.selectedDay).toBeNull();
      expect(() => mgr.setView("bogus")).not.toThrow();
      expect(mgr.viewMode).toBe("range");
    });

    test("onDayPillClick: en rango hace scroll, en horario cambia de día", () => {
      const scroll = jest
        .spyOn(mgr, "scrollToDay")
        .mockImplementation(() => {});
      try {
        mgr.onDayPillClick("2026-10-08");
        expect(scroll).toHaveBeenCalledWith("2026-10-08");

        mgr.setView("day");
        mgr.onDayPillClick("2026-10-09");
        expect(mgr.selectedDay).toBe("2026-10-09");
        expect(scroll).toHaveBeenCalledTimes(1);
      } finally {
        scroll.mockRestore();
      }
    });

    test("isDayActive marca el día seleccionado solo en modo horario", () => {
      expect(mgr.isDayActive("2026-10-07")).toBe(false);
      mgr.activeDay = "2026-10-07";
      expect(mgr.isDayActive("2026-10-07")).toBe(true); // modo rango: scroll

      mgr.setView("day", "2026-10-09");
      expect(mgr.isDayActive("2026-10-07")).toBe(false);
      expect(mgr.isDayActive("2026-10-09")).toBe(true);
    });
  });

  // --- Vista de horario de un día (carriles para lo simultáneo) ------------
  describe("daySchedule", () => {
    const DAY = "2026-10-08";

    function mount(activities) {
      mgr.calendar = {
        event: { id: 3, name: "46 Aniversario" },
        days: ["2026-10-07", DAY],
        activities,
        total_activities: activities.length,
      };
      return mgr.daySchedule(DAY);
    }

    beforeEach(() => {
      mount([
        { id: 1, day: DAY, starts_at: "09:00", ends_at: "11:00", name: "A" },
        { id: 2, day: DAY, starts_at: "10:00", ends_at: "12:00", name: "B" },
        { id: 3, day: DAY, starts_at: "13:00", ends_at: "14:00", name: "C" },
        { id: 4, day: DAY, starts_at: null, ends_at: null, name: "D" },
        { id: 5, day: DAY, starts_at: "15:00", ends_at: "15:00", name: "E" },
      ]);
    });

    test("reparte en carriles solo lo que se solapa", () => {
      const sch = mgr.daySchedule(DAY);
      const byId = Object.fromEntries(sch.items.map((i) => [i.id, i]));

      // 09:00–11:00 y 10:00–12:00 se solapan → carriles 0 y 1
      expect(byId[1].lane).toBe(0);
      expect(byId[2].lane).toBe(1);
      expect(byId[1].lanes).toBe(2);
      expect(byId[2].lanes).toBe(2);

      // 13:00 no toca a nadie → carril 0, solo en su tramo
      expect(byId[3].lane).toBe(0);
      expect(byId[3].lanes).toBe(1);

      expect(sch.maxLanes).toBe(2);
    });

    test("las no simultáneas no heredan los carriles del tramo anterior", () => {
      const sch = mgr.daySchedule(DAY);
      const c = sch.items.find((i) => i.id === 3);
      expect(c.lane).toBe(0);
      expect(c.lanes).toBe(1);
    });

    test("la ventana horaria va de la primera hora al último fin", () => {
      const sch = mgr.daySchedule(DAY);
      expect(sch.hourFrom).toBe(9); // primera inicio: 09:00
      // 15:00–15:00 no parsea como fin válido → se asume 1 h → cierra 16:00
      expect(sch.hourTo).toBe(16);
      expect(sch.hours).toEqual([9, 10, 11, 12, 13, 14, 15]);
      expect(sch.height).toBe(7 * 88);
      expect(sch.hourPx).toBe(88); // zoom del eje (antes 64)
    });

    test("la posición usa top/height en px y lane/lanes en %", () => {
      const sch = mgr.daySchedule(DAY);
      const a = sch.items.find((i) => i.id === 1);
      expect(a.style).toContain("top:0px");
      expect(a.style).toContain("height:176px"); // 2 h
      expect(a.style).toContain("left:calc(0.0000% + 2px)");
      expect(a.style).toContain("width:calc(50.0000% - 4px)");
      // geom es lo que cardStyle() recompone al pasar el cursor
      expect(a.geom).toEqual({
        top: 0,
        height: 176,
        leftPct: "0.0000",
        widthPct: "50.0000",
      });

      const b = sch.items.find((i) => i.id === 2);
      expect(b.style).toContain("left:calc(50.0000% + 2px)");
      expect(b.style).toContain("top:88px"); // arranca 1 h después
    });

    test("un fin igual al inicio se asume de 1 hora", () => {
      const sch = mgr.daySchedule(DAY);
      const e = sch.items.find((i) => i.id === 5);
      expect(e.style).toContain("height:88px"); // 15:00 → 16:00
      expect(e.style).toContain("top:528px"); // 15:00 - 09:00 = 6 h
    });

    test("una sesión muy corta no desaparece del lienzo", () => {
      const sch = mount([
        {
          id: 40,
          day: DAY,
          starts_at: "09:00",
          ends_at: "09:10",
          name: "Flash",
        },
      ]);
      expect(sch.items[0].style).toContain("top:0px");
      expect(sch.items[0].style).toContain("height:26px"); // mínimo visible
    });

    test("las actividades sin hora de inicio van a 'unscheduled'", () => {
      const sch = mgr.daySchedule(DAY);
      expect(sch.unscheduled.map((a) => a.id)).toEqual([4]);
      expect(sch.items.map((i) => i.id)).toEqual([1, 2, 3, 5]);
    });

    test("sin calendario devuelve una ventana por defecto vacía", () => {
      mgr.calendar = null;
      const sch = mgr.daySchedule(DAY);
      expect(sch.items).toEqual([]);
      expect(sch.unscheduled).toEqual([]);
      expect(sch.maxLanes).toBe(1);
      expect(sch.hourFrom).toBe(8);
      expect(sch.hourTo).toBe(18);
    });

    test("una sesión que cruza la medianoche se recorta al cierre del día", () => {
      const sch = mount([
        {
          id: 9,
          day: DAY,
          starts_at: "23:00",
          ends_at: "01:00",
          name: "Madrugada",
        },
      ]);
      expect(sch.hourFrom).toBe(23);
      expect(sch.hourTo).toBe(24);
      expect(sch.items[0].style).toContain("height:88px");
    });

    test("cachea el resultado por (calendar, día) para no recomputar", () => {
      const first = mgr.daySchedule(DAY);
      expect(mgr.daySchedule(DAY)).toBe(first);
      // Otro día → otra clave
      expect(mgr.daySchedule("2026-10-07")).not.toBe(first);
      // Otro calendario (recarga) invalida la caché
      mount([{ id: 50, day: DAY, starts_at: "08:00", ends_at: "09:00" }]);
      const fresh = mgr.daySchedule(DAY);
      expect(fresh).not.toBe(first);
      expect(fresh.items.map((i) => i.id)).toEqual([50]);
    });

    test("_toMin/hourLabel normalizan las horas", () => {
      expect(mgr._toMin("09:00")).toBe(540);
      expect(mgr._toMin("23:59")).toBe(1439);
      expect(mgr._toMin("9:05")).toBe(545);
      expect(mgr._toMin("")).toBeNull();
      expect(mgr._toMin(null)).toBeNull();
      expect(mgr._toMin("25:00")).toBeNull();
      expect(mgr._toMin("09:75")).toBeNull();
      expect(mgr.hourLabel(8)).toBe("08:00");
      expect(mgr.hourLabel(17)).toBe("17:00");
    });

    test("hourTop posiciona la hora respecto al inicio de la ventana", () => {
      mgr.setView("day", DAY);
      expect(mgr.hourTop(9)).toBe("0px");
      expect(mgr.hourTop(10)).toBe("88px");
      expect(mgr.hourTop(14)).toBe("440px");
    });
  });

  // --- Tarjeta angosta: título girado de abajo hacia arriba ---------------
  describe("isNarrow / schedText", () => {
    const DAY = "2026-10-08";

    function mount(n) {
      mgr.hoveredId = null;
      mgr.calendar = {
        event: { id: 3, name: "46 Aniversario" },
        days: [DAY],
        activities: Array.from({ length: n }, (_, k) => ({
          id: 100 + k,
          day: DAY,
          starts_at: "09:00",
          ends_at: "11:00",
          name: `Act ${k}`,
          location: "Sala 1",
          max_capacity: 30,
          registered_count: 12,
          session_index: 1,
          session_total: 2,
        })),
        total_activities: n,
      };
      mgr.selectedDay = DAY;
      return mgr.daySchedule(DAY);
    }

    test("1 o pocos carriles: tarjeta ancha, título en horizontal", () => {
      expect(mgr.isNarrow(mount(1).items[0])).toBe(false);
      expect(mgr.isNarrow(mount(3).items[0])).toBe(false);
      expect(mgr.isNarrow(mount(5).items[0])).toBe(false);
    });

    test("6 o más carriles: la tarjeta se angosta y el texto se gira", () => {
      const sch = mount(6);
      expect(sch.maxLanes).toBe(6);
      expect(sch.items.every((i) => mgr.isNarrow(i))).toBe(true);
      expect(mgr.isNarrow(null)).toBe(false);
      expect(mgr.isNarrow({ lanes: "19" })).toBe(true); // normaliza a número
    });

    // Un item suelto con la duración que queramos probar
    function dur(hours, extra) {
      return {
        lanes: 1,
        activity: Object.assign(
          {
            starts_at: "09:00",
            ends_at: String(9 + hours).padStart(2, "0") + ":00",
            name: "Nombre",
            location: "Sala 1",
            max_capacity: 30,
            registered_count: 12,
            session_index: 2,
            session_total: 3,
          },
          extra || {},
        ),
      };
    }

    test("schedText: el nombre va PRIMERO — en un timeline la hora ya la dice la posición", () => {
      const sch = mount(6);
      const text = mgr.schedText(sch.items[0]);
      expect(text).toBe("Act 0 · 09:00 – 11:00");
      expect(text.indexOf("Act 0")).toBe(0);
    });

    test("tier < 4 h: solo nombre y horario (la hora delantera se comía el nombre)", () => {
      expect(mgr.schedTier(dur(1))).toBe(0);
      expect(mgr.schedTier(dur(3))).toBe(0);
      const text = mgr.schedText(dur(1));
      expect(text).toBe("Nombre · 09:00 – 10:00");
      // ubicación, cupo y sesión se quedan para la tarjeta expandida
      expect(text).not.toContain("Sala 1");
      expect(text).not.toContain("12/30");
      expect(text).not.toContain("Sesión 2/3");
    });

    test("tier >= 4 h: añade ubicación, cupo y sesión", () => {
      expect(mgr.schedTier(dur(4))).toBe(1);
      expect(mgr.schedTier(dur(7))).toBe(1);
      expect(mgr.schedText(dur(7))).toBe(
        "Nombre · 09:00 – 16:00 · Sala 1 · 12/30 · Sesión 2/3",
      );
    });

    test("schedMinWidth garantiza carriles de al menos 56 px", () => {
      mount(1);
      expect(mgr.schedMinWidth()).toBe(680); // suelo
      mount(6);
      expect(mgr.schedMinWidth()).toBe(680); // 56 + 6*56 = 392 < suelo
      mount(19);
      expect(mgr.schedMinWidth()).toBe(56 + 19 * 56); // 1120, antes 680
      // Con el lienzo en su ancho mínimo, el carril mide LANE_MIN_PX:
      // 44 px de texto / 14 px de interlínea = 3 columnas (antes, 1).
      const lanes = mgr.daySchedule(DAY).maxLanes;
      expect((mgr.schedMinWidth() - 56) / lanes).toBe(56);
    });

    test("cardStyle ensancha la tarjeta bajo el cursor y sube su z-index", () => {
      const ev = mount(6).items[0];
      const base = mgr.cardStyle(ev);
      expect(base).toBe(ev.style);
      expect(base).toContain("width:calc(16.6667% - 4px)");
      expect(base).not.toContain("z-index");

      mgr.hoverOn(ev);
      expect(mgr.isHovered(ev)).toBe(true);
      const hov = mgr.cardStyle(ev);
      expect(hov).toContain("width:240px");
      expect(hov).toContain("z-index:40");
      // la posición no se mueve: crece hacia la derecha, sobre los vecinos
      expect(hov).toContain("top:0px");
      expect(hov).toContain("left:calc(0.0000% + 2px)");

      mgr.hoverOff(ev);
      expect(mgr.isHovered(ev)).toBe(false);
      expect(mgr.cardStyle(ev)).toBe(base);
      expect(mgr.cardStyle(null)).toBe("");
    });

    test("al pasar el cursor la tarjeta angosta muestra su contenido horizontal", () => {
      const sch = mount(6);
      const [a, b] = sch.items;
      expect(mgr.showNarrow(a)).toBe(true);
      expect(mgr.showWide(a)).toBe(false);

      mgr.hoverOn(a);
      expect(mgr.showNarrow(a)).toBe(false);
      expect(mgr.showWide(a)).toBe(true);
      // el hover de una tarjeta no afecta a las demás
      expect(mgr.isHovered(b)).toBe(false);
      expect(mgr.showNarrow(b)).toBe(true);

      mgr.hoverOff(a);
      expect(mgr.showNarrow(a)).toBe(true);

      // una tarjeta ancha no cambia al pasar el cursor
      const wide = mount(2).items[0];
      expect(mgr.showWide(wide)).toBe(true);
      expect(mgr.showNarrow(wide)).toBe(false);
      mgr.hoverOn(wide);
      expect(mgr.showWide(wide)).toBe(true);
      expect(mgr.showNarrow(wide)).toBe(false);
    });

    function mountSpan(start, end) {
      mgr.hoveredId = null;
      mgr.calendar = {
        event: {},
        days: [DAY],
        activities: [
          {
            id: 100,
            day: DAY,
            starts_at: start,
            ends_at: end,
            name: "Act",
            activity_type: "Magistral",
          },
        ],
        total_activities: 1,
      };
      mgr.selectedDay = DAY;
      return mgr.daySchedule(DAY).items[0];
    }

    test("los bloques extra de la ficha se habilitan por ALTURA, no por ancho", () => {
      // 1 h → 88 px: ni ubicación ni bloque profundo (si se metieran, la
      // última fila quedaría cortada por la mitad; la altura la fija el eje)
      const one = mountSpan("09:00", "10:00");
      expect(one.geom.height).toBe(88);
      expect(mgr.showLocRow(one)).toBe(false);
      expect(mgr.showDeepRow(one)).toBe(false);

      // 2 h → 176 px: ubicación + modalidad, sin descripción
      const two = mountSpan("09:00", "11:00");
      expect(two.geom.height).toBe(176);
      expect(mgr.showLocRow(two)).toBe(true);
      expect(mgr.showDeepRow(two)).toBe(false);

      // 3 h → 264 px: ficha completa
      const three = mountSpan("09:00", "12:00");
      expect(three.geom.height).toBe(264);
      expect(mgr.showLocRow(three)).toBe(true);
      expect(mgr.showDeepRow(three)).toBe(true);
      expect(mgr.showReqRow(three)).toBe(false);

      // 4 h → 352 px: se añaden los requisitos
      const four = mountSpan("09:00", "13:00");
      expect(four.geom.height).toBe(352);
      expect(mgr.showReqRow(four)).toBe(true);

      expect(mgr.showLocRow(null)).toBe(false);
      expect(mgr.showDeepRow({ lanes: 1 })).toBe(false);
      expect(mgr.showReqRow(null)).toBe(false);
    });

    test("speakersLine junta los nombres y tolera datos sucios", () => {
      expect(mgr.speakersLine(null)).toBe("");
      expect(mgr.speakersLine({ activity: {} })).toBe("");
      expect(mgr.speakersLine({ activity: { speakers: "no-json" } })).toBe("");
      expect(
        mgr.speakersLine({
          activity: {
            speakers: [
              { name: "Ana", degree: "Mtra.", organization: "Tec" },
              { name: "Luis" },
              { name: "   " },
              "  Bruno ",
            ],
          },
        }),
      ).toBe("Ana · Luis · Bruno");
    });

    test("schedText omite lo que falta sin romperse", () => {
      const bare = { lanes: 1, activity: { starts_at: null, ends_at: null } };
      expect(mgr.schedText(bare)).toBe("— – —");
      expect(mgr.schedText(null)).toBe("");
      expect(
        mgr.schedText({ activity: { starts_at: "10:00", ends_at: "11:00" } }),
      ).toBe("10:00 – 11:00");
      expect(mgr.schedTier(null)).toBe(0);
    });
  });

  // --- Día activo en el índice sticky (columna visible en móvil) -----------
  describe("updateActiveDay / initDaySpy", () => {
    const rect = (left, right, top = 0, bottom = 100) => ({
      left,
      right,
      top,
      bottom,
      width: right - left,
      height: bottom - top,
    });

    function mountDom({ overflow }) {
      const scroller = document.createElement("div");
      scroller.setAttribute("data-cal-scroll", "");
      scroller.getBoundingClientRect = () => rect(0, 400, 0, 800);
      Object.defineProperty(scroller, "scrollWidth", {
        value: overflow ? 900 : 400,
        configurable: true,
      });
      Object.defineProperty(scroller, "clientWidth", {
        value: 400,
        configurable: true,
      });
      document.body.appendChild(scroller);

      mgr.calendar = {
        days: ["2026-10-07", "2026-10-08", "2026-10-09"],
        activities: [],
      };
      return scroller;
    }

    // Columna k visible en [left, right] dentro del viewport del contenedor
    function mountDayColumn(day, left, right) {
      const el = document.createElement("div");
      el.id = `cal-day-${day}`;
      el.getBoundingClientRect = () => rect(left, right);
      document.body.appendChild(el);
    }

    afterEach(() => {
      document.body.innerHTML = "";
    });

    test("no resalta nada cuando todas las columnas caben (escritorio)", () => {
      mountDom({ overflow: false });
      mountDayColumn("2026-10-07", -100, 200);
      mountDayColumn("2026-10-08", 210, 510);
      mountDayColumn("2026-10-09", 520, 820);

      mgr.updateActiveDay();
      expect(mgr.activeDay).toBeNull();
    });

    test("en móvil resalta la columna con más área visible", () => {
      mountDom({ overflow: true });
      mountDayColumn("2026-10-07", -300, 100); // 100 px visibles
      mountDayColumn("2026-10-08", 110, 510); // 290 px visibles (viewport 0..400)
      mountDayColumn("2026-10-09", 520, 920); // 0 px visibles

      mgr.updateActiveDay();
      expect(mgr.activeDay).toBe("2026-10-08");
    });

    test("sin contenedor o con menos de 2 días no resalta", () => {
      mgr.calendar = { days: ["2026-10-07"], activities: [] };
      mountDom({ overflow: true });
      mgr.updateActiveDay();
      expect(mgr.activeDay).toBeNull();

      document.body.innerHTML = "";
      mgr.calendar = { days: ["2026-10-07", "2026-10-08"], activities: [] };
      mgr.updateActiveDay();
      expect(mgr.activeDay).toBeNull();
    });

    test("en modo horario el scroll no cambia el día resaltado", () => {
      mountDom({ overflow: true });
      mountDayColumn("2026-10-07", -300, 100);
      mountDayColumn("2026-10-08", 110, 510);
      mountDayColumn("2026-10-09", 520, 920);

      mgr.viewMode = "day"; // no hay columnas: el día lo decide selectedDay
      mgr.updateActiveDay();
      expect(mgr.activeDay).toBeNull();
    });

    test("initDaySpy/destroyDaySpy registran y quitan los listeners", () => {
      const scroller = mountDom({ overflow: true });
      const add = jest.spyOn(window, "addEventListener");
      const remove = jest.spyOn(window, "removeEventListener");
      const addEl = jest.spyOn(scroller, "addEventListener");
      const removeEl = jest.spyOn(scroller, "removeEventListener");
      try {
        mgr.initDaySpy();
        expect(add.mock.calls.map((c) => c[0])).toEqual(
          expect.arrayContaining(["resize", "beforeunload"]),
        );
        expect(addEl).toHaveBeenCalled();
        expect(mgr._spyHandler).toBeTruthy();

        // Idempotente: no duplica listeners
        const total = addEl.mock.calls.length;
        mgr.initDaySpy();
        expect(addEl.mock.calls.length).toBe(total);

        const handler = mgr._spyHandler;
        mgr.destroyDaySpy();
        expect(remove.mock.calls.map((c) => c[0])).toEqual(
          expect.arrayContaining(["resize", "beforeunload"]),
        );
        expect(removeEl).toHaveBeenCalledWith("scroll", handler);
        expect(mgr._spyHandler).toBeNull();

        // Doble destrucción no revienta
        expect(() => mgr.destroyDaySpy()).not.toThrow();
      } finally {
        add.mockRestore();
        remove.mockRestore();
        addEl.mockRestore();
        removeEl.mockRestore();
      }
    });
  });
});
