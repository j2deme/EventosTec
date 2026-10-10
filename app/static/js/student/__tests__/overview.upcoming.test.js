/** Tests for the student overview "Próximos Eventos" loader */

/** @jest-environment jsdom */
jest.resetModules();

// El módulo no exporta por CommonJS: expone la factory en window
require("../overview");

describe("studentOverviewManager (Próximos Eventos)", () => {
  let mgr, origFetch;

  beforeEach(() => {
    jest.resetModules();
    require("../overview");
    mgr = window.studentOverviewManager();

    origFetch = global.fetch;
    window.getAuthToken = () => "tok";
    window.getAuthHeaders = () => ({ Authorization: "Bearer tok" });
  });

  afterEach(() => {
    global.fetch = origFetch;
    delete window.getAuthToken;
    delete window.getAuthHeaders;
  });

  function mockEventsResponse(events, capture) {
    global.fetch = jest.fn((url) => {
      if (capture) capture.url = url;
      if (String(url).startsWith("/api/events")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ events, total: events.length }),
        });
      }
      return Promise.resolve({ ok: false });
    });
  }

  test("incluye un evento activo que empezó ayer y aún no termina", async () => {
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    const in3 = new Date(now);
    in3.setDate(now.getDate() + 3);
    const events = [
      {
        id: 46,
        name: "46 Aniversario",
        start_date: yesterday.toISOString(),
        end_date: in3.toISOString(),
        is_active: true,
      },
    ];
    mockEventsResponse(events);

    await mgr.loadUpcomingEvents();

    expect(mgr.upcomingEvents.map((e) => e.id)).toEqual([46]);
    expect(mgr.loadingUpcoming).toBe(false);
  });

  test("excluye eventos que ya terminaron", async () => {
    const now = new Date();
    const started = new Date(now);
    started.setDate(now.getDate() - 10);
    const ended = new Date(now);
    ended.setDate(now.getDate() - 5);
    const events = [
      {
        id: 1,
        name: "Terminado",
        start_date: started.toISOString(),
        end_date: ended.toISOString(),
        is_active: true,
      },
    ];
    mockEventsResponse(events);

    await mgr.loadUpcomingEvents();

    expect(mgr.upcomingEvents).toEqual([]);
  });

  test("usa el endpoint de lookup: lista completa sin paginar", async () => {
    const capture = {};
    mockEventsResponse([], capture);

    await mgr.loadUpcomingEvents();

    // Antes se subía per_page para no perder eventos más allá de la página 1.
    // El lookup devuelve la lista completa, así que no hay paginación que
    // ajustar: no debe llevar per_page=.
    expect(capture.url).toContain("/api/events/lookup");
    expect(capture.url).not.toContain("per_page=");
  });
});
