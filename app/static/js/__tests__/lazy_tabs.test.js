/**
 * Fase D — Lazy-init de pestañas del dashboard.
 *
 * Contrato:
 *  - La raíz (adminDashboard.initDashboard / studentDashboard.init) activa
 *    `window.__LAZY_TABS__` y despacha `tab:activated` con detail.tab.
 *  - Los parciales usan `window.tabLazyBoot(tab, boot)` (app.js): sin el
 *    flag arrancan de inmediato (comportamiento previo); con el flag, difieren
 *    el arranque hasta la primera activación de su pestaña (one-shot).
 *  - Los listeners (wiring) siempre quedan registrados en init().
 */

// app.js define window.tabLazyBoot y los helpers globales (una sola vez)
require("../app.js");

// app.js instala el showToast real (que llama a Toastify como constructor);
// restaurar el mock del setup para que ninguna ruta de error reviente tests
window.showToast = jest.fn();

const flush = () => new Promise((r) => setTimeout(r, 0));

function mockFetch() {
  const fetchMock = jest.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      events: [],
      activities: [],
      registrations: [],
      students: [],
      careers: [],
      settings: [],
      total: 0,
      page: 1,
      pages: 1,
    }),
  }));
  global.fetch = fetchMock;
  window.safeFetch = fetchMock;
  return fetchMock;
}

// Respuesta válida para /api/auth/profile (evita la ruta de error con toast)
function mockProfileFetch() {
  const fetchMock = jest.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      student: {
        id: 1,
        control_number: "A00000",
        full_name: "Estudiante Prueba",
        career: "Ingeniería",
        email: "test@example.com",
      },
    }),
  }));
  global.fetch = fetchMock;
  window.safeFetch = fetchMock;
  return fetchMock;
}

beforeEach(() => {
  jest.resetModules();
  delete window.__LAZY_TABS__;
  localStorage.clear();
  history.replaceState(null, "", "/");
  mockFetch();
});

describe("tabLazyBoot (helper global de app.js)", () => {
  test("sin __LAZY_TABS__: arranca inmediatamente y devuelve el resultado", async () => {
    const boot = jest.fn(() => "ok");
    const result = await window.tabLazyBoot("events", boot);
    expect(boot).toHaveBeenCalledTimes(1);
    expect(result).toBe("ok");
  });

  test("con __LAZY_TABS__: difiere hasta 'tab:activated' con la pestaña correcta y es one-shot", async () => {
    window.__LAZY_TABS__ = true;
    const boot = jest.fn();
    const pending = window.tabLazyBoot("events", boot);

    await flush();
    expect(boot).not.toHaveBeenCalled();

    // pestaña equivocada: no arranca
    window.dispatchEvent(
      new CustomEvent("tab:activated", { detail: { tab: "calendar" } }),
    );
    await flush();
    expect(boot).not.toHaveBeenCalled();

    // pestaña correcta: arranca una vez
    window.dispatchEvent(
      new CustomEvent("tab:activated", { detail: { tab: "events" } }),
    );
    await pending;
    expect(boot).toHaveBeenCalledTimes(1);

    // segunda visita: no re-arranca (one-shot)
    window.dispatchEvent(
      new CustomEvent("tab:activated", { detail: { tab: "events" } }),
    );
    await flush();
    expect(boot).toHaveBeenCalledTimes(1);
  });

  test("con array de pestañas acepta cualquiera ('reports' o 'report')", async () => {
    window.__LAZY_TABS__ = true;
    const boot = jest.fn();
    const pending = window.tabLazyBoot(["reports", "report"], boot);
    window.dispatchEvent(
      new CustomEvent("tab:activated", { detail: { tab: "report" } }),
    );
    await pending;
    expect(boot).toHaveBeenCalledTimes(1);
  });
});

describe("eventsManager (admin) — lazy-init", () => {
  test("sin flag: init() carga los datos inmediatamente (comportamiento previo)", async () => {
    const fetchMock = global.fetch;
    const eventsManager = require("../admin/events.js");
    const mgr = eventsManager();
    await mgr.init();
    expect(fetchMock).toHaveBeenCalled();
    expect(mgr._booted).toBe(true);
  });

  test("con flag: init() difiere la carga; el listener de edit-request sigue activo y fuerza el boot único", async () => {
    window.__LAZY_TABS__ = true;
    const fetchMock = global.fetch;
    const eventsManager = require("../admin/events.js");
    const mgr = eventsManager();
    mgr.openEditModal = jest.fn();

    mgr.init(); // no se await: en modo lazy queda pendiente hasta visitar la pestaña
    await flush();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(mgr._booted).toBeFalsy();

    // pestaña equivocada: no arranca
    window.dispatchEvent(
      new CustomEvent("tab:activated", { detail: { tab: "students" } }),
    );
    await flush();
    expect(fetchMock).not.toHaveBeenCalled();

    // el listener sigue activo sin boot y fuerza la carga del listado
    window.dispatchEvent(
      new CustomEvent("event:edit-request", {
        detail: { event: { id: 99, name: "Evento" } },
      }),
    );
    await flush();
    expect(mgr.openEditModal).toHaveBeenCalledWith({ id: 99, name: "Evento" });
    expect(fetchMock).toHaveBeenCalled();
    expect(mgr._booted).toBe(true);
    const callsAfterBoot = fetchMock.mock.calls.length;

    // al activar la pestaña no vuelve a cargar (boot idempotente)
    window.dispatchEvent(
      new CustomEvent("tab:activated", { detail: { tab: "events" } }),
    );
    await flush();
    expect(fetchMock.mock.calls.length).toBe(callsAfterBoot);
  });

  test("con flag: activar la pestaña 'events' dispara la carga", async () => {
    window.__LAZY_TABS__ = true;
    const fetchMock = global.fetch;
    const eventsManager = require("../admin/events.js");
    const mgr = eventsManager();

    mgr.init();
    await flush();
    expect(fetchMock).not.toHaveBeenCalled();

    window.dispatchEvent(
      new CustomEvent("tab:activated", { detail: { tab: "events" } }),
    );
    await flush();
    expect(fetchMock).toHaveBeenCalled();
  });
});

describe("registrationsManager (admin) — guard de attendance:changed", () => {
  test("con flag: no recarga antes del boot; tras el boot sí", async () => {
    window.__LAZY_TABS__ = true;
    const registrationsManager = require("../admin/registrations.js");
    const mgr = registrationsManager();
    mgr.loadRegistrations = jest.fn();

    mgr.init();
    await flush();
    expect(mgr.loadRegistrations).not.toHaveBeenCalled();

    // listener registrado pero la pestaña no ha sido visitada: se omite
    window.dispatchEvent(
      new CustomEvent("attendance:changed", { detail: {} }),
    );
    await flush();
    expect(mgr.loadRegistrations).not.toHaveBeenCalled();

    // boot vía pestaña
    window.dispatchEvent(
      new CustomEvent("tab:activated", { detail: { tab: "registrations" } }),
    );
    await flush();
    expect(mgr.loadRegistrations).toHaveBeenCalledTimes(1);

    // tras el boot el listener vuelve a recargar normalmente
    window.dispatchEvent(
      new CustomEvent("attendance:changed", { detail: {} }),
    );
    await flush();
    expect(mgr.loadRegistrations).toHaveBeenCalledTimes(2);
  });
});

describe("adminDashboard (raíz) — despacho de pestañas", () => {
  test("setActiveTab despacha 'tab:activated' e incluye la pestaña 'calendar'", () => {
    const adminDashboard = require("../admin/dashboard.js");
    const mgr = adminDashboard();
    const received = [];
    const onTab = (e) => received.push(e.detail.tab);
    window.addEventListener("tab:activated", onTab);

    // regresión del fix: 'calendar' debe ser una pestaña válida
    expect(mgr.isValidTab("calendar")).toBe(true);
    mgr.setActiveTab("calendar");
    expect(received[received.length - 1]).toBe("calendar");

    mgr.setActiveTab("events");
    expect(received[received.length - 1]).toBe("events");

    // pestaña inválida: no cambia ni despacha
    const before = received.length;
    mgr.setActiveTab("nope");
    expect(received.length).toBe(before);

    window.removeEventListener("tab:activated", onTab);
  });

  test("initDashboard activa __LAZY_TABS__ y despacha la pestaña inicial en un microtask", async () => {
    delete window.__LAZY_TABS__;
    const adminDashboard = require("../admin/dashboard.js");
    const mgr = adminDashboard();
    mgr.loadDashboardData = jest.fn(); // evitar fetch del dashboard

    const received = [];
    const onTab = (e) => received.push(e.detail.tab);
    window.addEventListener("tab:activated", onTab);

    await mgr.initDashboard();
    expect(window.__LAZY_TABS__).toBe(true);
    await flush();
    expect(received).toEqual(["overview"]);

    window.removeEventListener("tab:activated", onTab);
  });

  test("integración: la raíz activa el flag y setActiveTab arranca el parcial", async () => {
    const fetchMock = global.fetch;
    const adminDashboard = require("../admin/dashboard.js");
    const eventsManager = require("../admin/events.js");

    const root = adminDashboard();
    root.loadDashboardData = jest.fn();
    await root.initDashboard();

    const partial = eventsManager();
    partial.init(); // lazy: no carga aún
    await flush();
    expect(fetchMock).not.toHaveBeenCalled();

    root.setActiveTab("events");
    await flush();
    expect(fetchMock).toHaveBeenCalled();
  });
});

describe("studentDashboard (raíz) — despacho de pestañas", () => {
  test("init activa __LAZY_TABS__ y despacha la pestaña inicial", async () => {
    window.checkAuthAndRedirect = jest.fn(() => true);
    require("../student/dashboard.js");
    const mgr = window.studentDashboard();
    mgr.loadStudentProfile = jest.fn();

    const received = [];
    const onTab = (e) => received.push(e.detail.tab);
    window.addEventListener("tab:activated", onTab);

    mgr.init();
    expect(window.__LAZY_TABS__).toBe(true);
    await flush();
    expect(received).toEqual(["overview"]);

    window.removeEventListener("tab:activated", onTab);
  });

  test("setActiveTab despacha con la pestaña destino", () => {
    require("../student/dashboard.js");
    const mgr = window.studentDashboard();
    const received = [];
    const onTab = (e) => received.push(e.detail.tab);
    window.addEventListener("tab:activated", onTab);

    mgr.setActiveTab("history");
    expect(received[received.length - 1]).toBe("history");

    window.removeEventListener("tab:activated", onTab);
  });
});

describe("studentProfileManager (student) — lazy-init", () => {
  test("sin flag: init() carga el perfil inmediatamente", async () => {
    localStorage.setItem("authToken", "test-token");
    const fetchMock = mockProfileFetch();
    require("../student/profile.js");
    const mgr = window.studentProfileManager();
    mgr.init();
    await flush();
    expect(fetchMock).toHaveBeenCalled();
    expect(mgr.studentData.full_name).toBe("Estudiante Prueba");
  });

  test("con flag: init() difiere la carga hasta la pestaña 'profile'", async () => {
    window.__LAZY_TABS__ = true;
    localStorage.setItem("authToken", "test-token");
    const fetchMock = mockProfileFetch();
    require("../student/profile.js");
    const mgr = window.studentProfileManager();

    mgr.init();
    await flush();
    expect(fetchMock).not.toHaveBeenCalled();

    window.dispatchEvent(
      new CustomEvent("tab:activated", { detail: { tab: "profile" } }),
    );
    await flush();
    expect(fetchMock).toHaveBeenCalled();
  });
});
