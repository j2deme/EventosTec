// helpers/dateHelpers.js
// ─────────────────────────────────────────────────────────────────────────────
// ÚNICA fuente de formateo de fechas del frontend.
//
// Convención canónica de presentación (decisión de producto):
//   · Locale: es-MX en todo el frontend.
//   · Hora: formato 24 h "09:00" (hourCycle h23) — sin a. m./p. m.
//   · Fechas puras "YYYY-MM-DD": se parsean SIEMPRE como fechas locales.
//     new Date("2026-10-08") es medianoche UTC y en zonas al oeste de UTC
//     (América) retrocedía al día anterior — el encabezado del 8 de octubre
//     se mostraba como "7 de octubre".
//
// Formatos canónicos:
//   formatDate             → "8 de octubre de 2026"
//   formatOnlyDate         → "8 de octubre de 2026" (alias histórica)
//   formatDateShort        → "8 oct 2026"
//   formatTime             → "09:00"
//   formatDateTime         → "8 de octubre de 2026, 09:00"
//   formatDateTimeShort    → "8 oct 2026, 09:00"
//   formatShortDate        → "08/10/2026, 09:00"
//   formatDateTimeForInput → "2026-10-08T09:00" (input datetime-local)
//   dateKey                → "2026-10-08" (clave local de día)
// ─────────────────────────────────────────────────────────────────────────────
(function () {
  if (
    typeof window !== "undefined" &&
    window.dateHelpers &&
    window.dateHelpers.__initialized
  ) {
    // Si estamos en un entorno CommonJS, también exportamos la referencia existente
    if (typeof module !== "undefined" && module.exports)
      module.exports = window.dateHelpers;
    return;
  }

  const LOCALE = "es-MX";
  // hourCycle h23 = 24 h siempre con dos dígitos ("09:00"), evita el
  // "24:00" que produce hour12:false en algunos entornos.
  const HOUR24 = { hour: "2-digit", minute: "2-digit", hourCycle: "h23" };

  const hasDayjs = typeof dayjs !== "undefined";
  try {
    if (hasDayjs && typeof dayjs.locale === "function") dayjs.locale("es");
  } catch (e) {
    // no-op
  }

  const pad = (n) => String(n).padStart(2, "0");

  function _toDate(d) {
    if (d instanceof Date) return d;
    if (typeof d === "string") {
      const s = d.trim();
      // Fecha pura "YYYY-MM-DD": new Date() la interpreta como medianoche UTC
      // y en zonas al oeste de UTC (América) retrocede al día anterior.
      // Se construye como fecha LOCAL para que el día sea el mismo en toda
      // zona horaria. Los datetime con hora conservan el parseo normal.
      if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
        const [y, m, day] = s.split("-").map(Number);
        return new Date(y, m - 1, day);
      }
    }
    return new Date(d);
  }

  function _longDate(d) {
    // "8 de octubre de 2026"
    return d.toLocaleDateString(LOCALE, {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  }

  function formatDate(dateString) {
    if (!dateString) return "Sin fecha";
    const d = _toDate(dateString);
    if (isNaN(d)) return "Sin fecha";
    try {
      return _longDate(d);
    } catch (e) {
      if (hasDayjs) return dayjs(dateString).format("D [de] MMMM [de] YYYY");
      return d.toDateString();
    }
  }

  function formatOnlyDate(dateString) {
    // Alias histórica: mismo formato que formatDate.
    return formatDate(dateString);
  }

  function formatDateShort(dateString) {
    // "8 oct 2026"
    if (!dateString) return "Sin fecha";
    const d = _toDate(dateString);
    if (isNaN(d)) return "Sin fecha";
    try {
      return d.toLocaleDateString(LOCALE, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch (e) {
      if (hasDayjs) return dayjs(dateString).format("D MMM YYYY");
      return d.toDateString();
    }
  }

  function formatShortDate(dateString) {
    // "08/10/2026, 09:00"
    if (!dateString) return "Sin fecha";
    const d = _toDate(dateString);
    if (isNaN(d)) return "Sin fecha";
    try {
      return d.toLocaleString(LOCALE, {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        ...HOUR24,
      });
    } catch (e) {
      if (hasDayjs) return dayjs(dateString).format("DD/MM/YYYY HH:mm");
      return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${
        d.getFullYear()
      } ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }
  }

  function formatDateTime(dateString) {
    // "8 de octubre de 2026, 09:00"
    if (!dateString) return "Sin fecha";
    const d = _toDate(dateString);
    if (isNaN(d)) return "Sin fecha";
    try {
      return d.toLocaleString(LOCALE, {
        year: "numeric",
        month: "long",
        day: "numeric",
        ...HOUR24,
      });
    } catch (e) {
      if (hasDayjs)
        return dayjs(dateString).format("D [de] MMMM [de] YYYY, HH:mm");
      // Fallback manual: Intl acaba de fallar, no volver a usarlo
      return `${d.getDate()}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(
        d.getHours(),
      )}:${pad(d.getMinutes())}`;
    }
  }

  function formatDateTimeShort(dateString) {
    // "8 oct 2026, 09:00"
    if (!dateString) return "Sin fecha";
    const d = _toDate(dateString);
    if (isNaN(d)) return "Sin fecha";
    try {
      return d.toLocaleString(LOCALE, {
        year: "numeric",
        month: "short",
        day: "numeric",
        ...HOUR24,
      });
    } catch (e) {
      if (hasDayjs) return dayjs(dateString).format("D MMM YYYY, HH:mm");
      // Fallback manual: Intl acaba de fallar, no volver a usarlo
      const MONTHS_SHORT = [
        "ene", "feb", "mar", "abr", "may", "jun",
        "jul", "ago", "sept", "oct", "nov", "dic",
      ];
      return `${d.getDate()} ${
        MONTHS_SHORT[d.getMonth()]
      } ${d.getFullYear()}, ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }
  }

  function formatDateTimeForInput(dateTimeString) {
    if (!dateTimeString) return "";
    const d = _toDate(dateTimeString);
    if (isNaN(d)) return "";
    const year = d.getFullYear();
    const month = pad(d.getMonth() + 1);
    const day = pad(d.getDate());
    const hours = pad(d.getHours());
    const minutes = pad(d.getMinutes());
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  }

  function formatTime(dateString) {
    // "09:00"
    if (!dateString) return "--:--";
    const d = _toDate(dateString);
    if (isNaN(d)) return "--:--";
    try {
      return d.toLocaleTimeString(LOCALE, HOUR24);
    } catch (e) {
      if (hasDayjs) return dayjs(dateString).format("HH:mm");
      return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }
  }

  function dateKey(value) {
    // Clave local "YYYY-MM-DD" — usar SIEMPRE como clave de día para
    // agrupaciones/comparaciones (reemplaza split("T")[0] e
    // toISOString().split("T")[0], que dependen de la zona horaria).
    if (value === null || value === undefined || value === "") return "";
    const d = _toDate(value);
    if (isNaN(d)) return "";
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  const exported = {
    formatDate,
    formatShortDate,
    formatOnlyDate,
    formatDateShort,
    formatDateTime,
    formatDateTimeShort,
    formatDateTimeForInput,
    formatTime,
    dateKey,
    __initialized: true,
  };

  // Export for CommonJS (tests) and expose in browser as window.dateHelpers
  if (typeof module !== "undefined" && module.exports) {
    module.exports = exported;
  }

  if (typeof window !== "undefined") {
    // Do not overwrite an existing window.dateHelpers (defensive)
    window.dateHelpers = window.dateHelpers || exported;
    // Ensure flag set on the window object too so subsequent loads detect it
    window.dateHelpers.__initialized = true;
  }
})();
