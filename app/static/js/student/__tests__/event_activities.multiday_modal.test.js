/** C-0: el modal multídías de preregistro.
 *
 * Cubre los tres sub-problemas del hallazgo C-0 (el único bloqueante que
 * ningún test detectaba):
 *
 *   1. `activity.name` se inyectaba con `insertAdjacentHTML` SIN escapar:
 *      un nombre de actividad con HTML/JS se ejecutaba en el navegador del
 *      estudiante (XSS almacenado; lo escribe el administrador).
 *   2. `document.onkeydown` se asignaba y nunca se liberaba: el handler
 *      seguía vivo después del modal y pisaba cualquier otro manejo global
 *      de teclado.
 *   3. El guard `inflight` entraba DESPUÉS de abrir el modal, así que un
 *      doble clic dejaba dos modales con el mismo `id`.
 */

/** @jest-environment jsdom */
jest.resetModules();

// Convención del repo: mockear fetch/localStorage ANTES de requerir el módulo.
global.fetch = jest.fn();
global.localStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
};

require("../../helpers/activityTypeHelpers");
require("../event_activities");

const activity = (overrides = {}) => ({
  id: 1,
  name: "Taller de Excel",
  start_datetime: "2026-10-05T09:00:00",
  end_datetime: "2026-10-06T11:00:00",
  ...overrides,
});

const modal = () => document.getElementById("multiday-confirm-modal");

describe("showMultiDayConfirmation (C-0)", () => {
  let mgr;

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch.mockReset();
    mgr = window.studentEventActivitiesManager();
  });

  afterEach(() => {
    document.body.innerHTML = "";
    document.onkeydown = null;
  });

  // ── 1. XSS ────────────────────────────────────────────────────────────────

  test("el nombre de la actividad se inyecta como TEXTO, no como HTML", async () => {
    const evil = '<img src=x onerror="window.__xss = 1">';
    const promise = mgr.showMultiDayConfirmation(activity({ name: evil }));

    // No llega a crearse ningún elemento: el payload no se interpreta
    expect(document.querySelectorAll("img").length).toBe(0);
    expect(window.__xss).toBeUndefined();

    // Y el texto se ve escapado (no crudo)
    expect(modal().innerHTML).toContain("&lt;img src=x onerror=");
    expect(modal().innerHTML).not.toContain("<img src=x");

    document.getElementById("cancel-multiday-register").click();
    await expect(promise).resolves.toBe(false);
  });

  test("las fechas también pasan por escape", async () => {
    const promise = mgr.showMultiDayConfirmation(
      activity({
        start_datetime: "<script>window.__xss=1</script>",
        end_datetime: "</p><script>window.__xss=1</script>",
      }),
    );

    expect(document.querySelectorAll("script").length).toBe(0);
    expect(window.__xss).toBeUndefined();

    document.getElementById("cancel-multiday-register").click();
    await expect(promise).resolves.toBe(false);
  });

  // ── 2. Handler de teclado filtrado ────────────────────────────────────────

  test("Escape cierra el modal y LIBERA el handler de teclado", async () => {
    const removeSpy = jest.spyOn(document, "removeEventListener");
    const promise = mgr.showMultiDayConfirmation(activity());

    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
    await expect(promise).resolves.toBe(false);

    expect(removeSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
    // Nunca se usa el handler GLOBAL: eso es lo que pisaba a otros módulos
    expect(document.onkeydown).toBeNull();
    expect(modal()).toBeNull();
    expect(mgr.multiDayModalOpen).toBe(false);

    removeSpy.mockRestore();
  });

  test("un Escape posterior al cierre no vuelve a resolver ni lanza error", async () => {
    const promise = mgr.showMultiDayConfirmation(activity());

    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
    await expect(promise).resolves.toBe(false);

    // Segundo Escape: el listener ya fue retirado, no debe pasar nada
    expect(() =>
      document.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      ),
    ).not.toThrow();
    expect(document.querySelectorAll("#multiday-confirm-modal").length).toBe(0);
  });

  // ── 3. Doble modal con el mismo id ────────────────────────────────────────

  test("un segundo intento no deja un modal huérfano con el mismo id", async () => {
    mgr.showMultiDayConfirmation(activity());
    const second = mgr.showMultiDayConfirmation(activity());

    // Un solo nodo en el DOM: el anterior se retira antes de insertar
    expect(document.querySelectorAll("#multiday-confirm-modal").length).toBe(1);

    document.getElementById("cancel-multiday-register").click();
    await expect(second).resolves.toBe(false);
    expect(modal()).toBeNull();
  });

  test("registerForActivity con el modal abierto no abre otro ni llama a la API", async () => {
    mgr.multiDayModalOpen = true;

    await mgr.registerForActivity(activity({ id: 42 }));

    expect(document.querySelectorAll("#multiday-confirm-modal").length).toBe(0);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  // ── Caminos de cierre ─────────────────────────────────────────────────────

  test("confirmar resuelve true y libera el estado", async () => {
    const promise = mgr.showMultiDayConfirmation(activity());

    document.getElementById("confirm-multiday-register").click();

    await expect(promise).resolves.toBe(true);
    expect(modal()).toBeNull();
    expect(mgr.multiDayModalOpen).toBe(false);
  });

  test("cancelar resuelve false y libera el estado", async () => {
    const promise = mgr.showMultiDayConfirmation(activity());

    document.getElementById("cancel-multiday-register").click();

    await expect(promise).resolves.toBe(false);
    expect(modal()).toBeNull();
    expect(mgr.multiDayModalOpen).toBe(false);
  });
});
