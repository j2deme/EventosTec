// helpers/paginationHelpers.js
// ─────────────────────────────────────────────────────────────────────────────
// ÚNICA fuente de la ventana de páginas visible del paginador.
//
// Problema que resuelve: varias vistas construían la lista completa de páginas
// con `Array.from({ length: total_pages })`. Con 2252 estudiantes a 10 por
// página eso generaba 226 botones dentro de un <nav> sin límite de ancho, y la
// pantalla crecía hacia la derecha de forma ingobernable. El bug se replicó en
// 8 vistas porque el markup del paginador estaba copiado y pegado en cada una.
//
// Esta función devuelve SIEMPRE una ventana acotada, sin importar cuántas
// páginas existan. La garantía (ver maxWindowLength) es que el resultado nunca
// excede `2 * boundaries + 2 * siblings + 5` elementos.
//
// Formato del resultado: array de items con `key` única (para el `:key` de
// Alpine) y, o bien un `page` numérico, o bien `isEllipsis: true` para los
// puntos suspensivos clickeables que enfocan el input "Ir a página".
//
//   buildWindow(13, 226) →
//     [ {key:'p1',page:1}, {key:'p2',page:2}, {key:'e1',isEllipsis:true},
//       {key:'p12',page:12}, {key:'p13',page:13,isActive:true}, {key:'p14',page:14},
//       {key:'e2',isEllipsis:true}, {key:'p225',page:225}, {key:'p226',page:226} ]
//
// `buildState(data, perPage)` construye el objeto `pagination` completo que
// consumen los templates, y calcula `showJump`: si el input "Ir a página"
// debe mostrarse (solo cuando navegar de uno en uno con ‹ › es tedioso).
// ─────────────────────────────────────────────────────────────────────────────
(function () {
  if (
    typeof window !== "undefined" &&
    window.paginationHelpers &&
    window.paginationHelpers.__initialized
  ) {
    if (typeof module !== "undefined" && module.exports)
      module.exports = window.paginationHelpers;
    return;
  }

  // Cota superior del tamaño de la ventana. No es el tamaño típico (que es
  // 2*boundaries + 2*siblings + 1, o totalPages si cabe entero), sino el peor
  // caso: base + hasta 2 páginas rellenadas + hasta 2 puntos suspensivos.
  function maxWindowLength(boundaries, siblings) {
    const b = Math.max(0, toInt(boundaries, 2));
    const s = Math.max(0, toInt(siblings, 1));
    return 2 * b + 2 * s + 5;
  }

  // ¿Merece la pena mostrar el input "Ir a página"?
  function showJumpInput(total, threshold) {
    const t = toInt(threshold, 12);
    return toPositiveInt(total) > t;
  }

  // Entero con valor por defecto; devuelve `fallback` si no es numérico.
  function toInt(value, fallback) {
    if (typeof value === "number" && isFinite(value)) return Math.trunc(value);
    const n = parseInt(value, 10);
    return isFinite(n) ? n : fallback;
  }

  // Entero >= 1; cualquier basura se convierte en 1.
  function toPositiveInt(value) {
    const n = toInt(value, 1);
    return n < 1 ? 1 : n;
  }

  // Construye la ventana de páginas visibles.
  //
  //   current → página activa (1-based)
  //   total   → número total de páginas
  //   options → { siblings:  páginas a cada lado de la activa (default 1),
  //               boundaries: páginas fijas al inicio y al final (default 2) }
  function buildWindow(current, total, options) {
    const opts = options || {};
    const siblings = Math.max(0, toInt(opts.siblings, 1));
    const boundaries = Math.max(0, toInt(opts.boundaries, 2));

    const totalPages = toPositiveInt(total);
    const active = Math.min(toPositiveInt(current), totalPages);

    // 1) Páginas que deben aparecer sí o sí, en orden y sin duplicados.
    const wanted = [];
    const add = (p) => {
      if (p >= 1 && p <= totalPages && wanted.indexOf(p) === -1) wanted.push(p);
    };

    for (let p = 1; p <= boundaries; p++) add(p);
    for (let p = active - siblings; p <= active + siblings; p++) add(p);
    for (let p = totalPages - boundaries + 1; p <= totalPages; p++) add(p);
    wanted.sort((a, b) => a - b);

    // 2) Recorrer rellenando huecos: de 1 en 1 no se marca nada; un hueco de
    //    exactamente una página se muestra como página (queda más claro que
    //    un "…"); cualquier hueco más grande se colapsa en puntos suspensivos.
    const items = [];
    let ellipsisSeq = 0;

    for (let i = 0; i < wanted.length; i++) {
      if (i > 0) {
        const gap = wanted[i] - wanted[i - 1];
        if (gap === 2) {
          wanted.splice(i, 0, wanted[i - 1] + 1);
        } else if (gap > 2) {
          items.push(makeEllipsis("e" + ++ellipsisSeq));
        }
      }
      items.push(makePage(wanted[i], active));
    }

    return items;
  }

  function makePage(page, active) {
    return {
      key: "p" + page,
      page: page,
      isActive: page === active,
    };
  }

  function makeEllipsis(id) {
    return {
      key: id,
      page: null,
      isEllipsis: true,
      isActive: false,
    };
  }

  // Construye el objeto `pagination` completo que consumen los templates a
  // partir de la respuesta paginada del backend. Centraliza el cálculo de
  // `from`/`to`, que antes estaba hardcodeado con "* 10" en cada vista y se
  // desincronizaba en cuanto cambiaba el número de filas por página.
  //
  //   data → { pages, current_page, total }  (respuesta del backend)
  //   perPage → filas por página reales
  function buildState(data, perPage, options) {
    const rows = Math.max(1, toInt(perPage, 10));
    const payload = data || {};
    const lastPage = toPositiveInt(payload.pages);
    const currentPage = Math.min(toPositiveInt(payload.current_page), lastPage);
    const total = Math.max(0, toInt(payload.total, 0));

    return {
      current_page: currentPage,
      last_page: lastPage,
      total: total,
      from: total === 0 ? 0 : (currentPage - 1) * rows + 1,
      to: Math.min(currentPage * rows, total),
      perPage: rows,
      window: buildWindow(currentPage, lastPage, options),
      showJump: showJumpInput(lastPage),
    };
  }

  const exported = {
    buildWindow,
    buildState,
    showJumpInput,
    maxWindowLength,
    __initialized: true,
  };

  // Export for CommonJS (tests) and expose in browser as window.paginationHelpers
  if (typeof module !== "undefined" && module.exports) {
    module.exports = exported;
  }

  if (typeof window !== "undefined") {
    window.paginationHelpers = window.paginationHelpers || exported;
    window.paginationHelpers.__initialized = true;
  }
})();
