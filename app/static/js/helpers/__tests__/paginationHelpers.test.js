/** Tests del helper de ventana de páginas del paginador (compartido). */

/** @jest-environment jsdom */
jest.resetModules();

const paginationHelpers = require("../paginationHelpers");

const { buildWindow, showJumpInput, maxWindowLength } = paginationHelpers;

// Extrae solo los números de página, marcando los huecos como "…".
const asPages = (items) => items.map((it) => (it.isEllipsis ? "…" : it.page));

describe("paginationHelpers.buildWindow", () => {
  test("total pequeño: devuelve todas las páginas sin puntos suspensivos", () => {
    expect(asPages(buildWindow(1, 5))).toEqual([1, 2, 3, 4, 5]);
  });

  test("total = 1: una sola página", () => {
    expect(asPages(buildWindow(1, 1))).toEqual([1]);
    expect(buildWindow(1, 1)[0].isActive).toBe(true);
  });

  test("total basura (0, negativo, no numérico) se normaliza a 1", () => {
    expect(asPages(buildWindow(1, 0))).toEqual([1]);
    expect(asPages(buildWindow(1, -5))).toEqual([1]);
    expect(asPages(buildWindow(1, "abc"))).toEqual([1]);
    expect(asPages(buildWindow(1, null))).toEqual([1]);
  });

  test("página activa al inicio: borde izquierdo pegado, puntos a la derecha", () => {
    expect(asPages(buildWindow(1, 226))).toEqual([1, 2, "…", 225, 226]);
  });

  test("página activa al final: borde derecho pegado, puntos a la izquierda", () => {
    expect(asPages(buildWindow(226, 226))).toEqual([1, 2, "…", 225, 226]);
  });

  test("página activa al centro: ventana alrededor con puntos a ambos lados", () => {
    expect(asPages(buildWindow(13, 226))).toEqual([
      1,
      2,
      "…",
      12,
      13,
      14,
      "…",
      225,
      226,
    ]);
  });

  test("marca isActive solo en la página activa", () => {
    const items = buildWindow(13, 226);
    const active = items.filter((it) => it.isActive);
    expect(active).toHaveLength(1);
    expect(active[0].page).toBe(13);
  });

  test("página activa fuera de rango se recorta al total", () => {
    const items = buildWindow(999, 20);
    const active = items.find((it) => it.isActive);
    expect(active.page).toBe(20);
    expect(asPages(items)).toContain(20);
  });

  test("hueco de exactamente una página se muestra como página, no como puntos", () => {
    // boundaries=2 → [1,2]; central arranca en 4 → hueco de 1 (la 3) que se
    // rellena como página. El salto 6→11 sí es un hueco real: queda en "…".
    expect(asPages(buildWindow(5, 12, { siblings: 1, boundaries: 2 }))).toEqual(
      [1, 2, 3, 4, 5, 6, "…", 11, 12],
    );
  });

  test("huecos colapsados: nunca se imprime '…' pegado a un borde", () => {
    // 6→11 es hueco; si el central llegara hasta 10 no habría separador.
    expect(asPages(buildWindow(8, 12, { siblings: 2, boundaries: 2 }))).toEqual(
      [1, 2, "…", 6, 7, 8, 9, 10, 11, 12],
    );
  });

  test("keys siempre únicas (requisito del :key de Alpine)", () => {
    const items = buildWindow(57, 580, { siblings: 2, boundaries: 3 });
    const keys = items.map((it) => it.key);
    expect(new Set(keys).size).toBe(keys.length);
  });

  test("GARANTÍA: la ventana nunca crece con el total de páginas", () => {
    const cases = [
      [1, 10],
      [5, 50],
      [13, 226],
      [57, 580],
      [300, 5000],
      [1, 100000],
    ];

    cases.forEach(([current, total]) => {
      const items = buildWindow(current, total);
      expect(items.length).toBeLessThanOrEqual(maxWindowLength(2, 1));
    });
  });

  test("GARANTÍA: con siblings/boundaries personalizados también se acota", () => {
    [1, 3, 7, 250].forEach((current) => {
      const items = buildWindow(current, 1000, {
        siblings: 3,
        boundaries: 5,
      });
      expect(items.length).toBeLessThanOrEqual(maxWindowLength(5, 3));
    });
  });

  test("options inválidas caen a los defaults en vez de romper", () => {
    const items = buildWindow(13, 226, { siblings: "x", boundaries: -1 });
    expect(items.length).toBeLessThanOrEqual(maxWindowLength(0, 0));
    expect(asPages(items)).toContain(13);
  });

  test("sin segunda página no hay separadores colgantes", () => {
    expect(asPages(buildWindow(1, 2))).toEqual([1, 2]);
    expect(asPages(buildWindow(2, 2))).toEqual([1, 2]);
    expect(asPages(buildWindow(2, 3))).toEqual([1, 2, 3]);
  });
});

describe("paginationHelpers.buildState", () => {
  const resp = { pages: 226, current_page: 13, total: 2252 };

  test("calcula from/to con el perPage real (antes hardcodeado '* 10')", () => {
    const s = paginationHelpers.buildState(resp, 10);
    expect(s.from).toBe(121);
    expect(s.to).toBe(130);
  });

  test("from/to se adapta a 25 filas por página", () => {
    const s = paginationHelpers.buildState(resp, 25);
    expect(s.from).toBe(301);
    expect(s.to).toBe(325);
  });

  test("from/to se adapta a 100 filas por página", () => {
    const s = paginationHelpers.buildState(resp, 100);
    expect(s.from).toBe(1201);
    expect(s.to).toBe(1300);
  });

  test("la última página recorta `to` al total real", () => {
    const s = paginationHelpers.buildState(
      { pages: 226, current_page: 226, total: 2252 },
      10,
    );
    expect(s.from).toBe(2251);
    expect(s.to).toBe(2252);
  });

  test("listado vacío: from/to en 0, una sola página", () => {
    const s = paginationHelpers.buildState(
      { pages: 0, current_page: 1, total: 0 },
      10,
    );
    expect(s.from).toBe(0);
    expect(s.to).toBe(0);
    expect(s.last_page).toBe(1);
    expect(s.showJump).toBe(false);
  });

  test("la ventana viene acotada y `showJump` coincide con el total", () => {
    const s = paginationHelpers.buildState(resp, 10);
    expect(s.window.length).toBeLessThanOrEqual(maxWindowLength(2, 1));
    expect(s.showJump).toBe(true);
  });

  test("current_page fuera de rango se recorta a last_page", () => {
    const s = paginationHelpers.buildState(
      { pages: 5, current_page: 99, total: 50 },
      10,
    );
    expect(s.current_page).toBe(5);
  });

  test("respuestas malformadas no lanzan excepción", () => {
    expect(() => paginationHelpers.buildState(null, 10)).not.toThrow();
    expect(() => paginationHelpers.buildState({}, 10)).not.toThrow();
    const s = paginationHelpers.buildState({ pages: "x" }, "y");
    expect(s.last_page).toBe(1);
  });

  test("perPage inválido cae a 10 en vez de producir NaN", () => {
    const s = paginationHelpers.buildState(resp, undefined);
    expect(s.from).toBe(121);
    expect(s.to).toBe(130);
  });
});

describe("paginationHelpers.showJumpInput", () => {
  test("oculto para listados cortos", () => {
    expect(showJumpInput(1)).toBe(false);
    expect(showJumpInput(5)).toBe(false);
    expect(showJumpInput(12)).toBe(false);
  });

  test("visible cuando hay más páginas que el umbral", () => {
    expect(showJumpInput(13)).toBe(true);
    expect(showJumpInput(226)).toBe(true);
    expect(showJumpInput(580)).toBe(true);
  });

  test("umbral configurable", () => {
    expect(showJumpInput(25, 20)).toBe(true);
    expect(showJumpInput(25, 30)).toBe(false);
  });

  test("entradas basura no lanzan excepción", () => {
    expect(showJumpInput(undefined)).toBe(false);
    expect(showJumpInput("abc")).toBe(false);
  });
});

describe("paginationHelpers.maxWindowLength", () => {
  test("crece linealmente con boundaries y siblings", () => {
    expect(maxWindowLength(2, 1)).toBe(11);
    expect(maxWindowLength(0, 0)).toBe(5);
    expect(maxWindowLength(5, 3)).toBe(21);
  });
});
