// helpers/dateHelpers.js
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

  // Funciones de formateo de fecha centralizadas; usan dayjs si está disponible
  const hasDayjs = typeof dayjs !== "undefined";
  try {
    if (hasDayjs && typeof dayjs.locale === "function") dayjs.locale("es");
  } catch (e) {
    // no-op
  }

  function _toDate(d) {
    if (d instanceof Date) return d;
    return new Date(d);
  }

  function formatDate(dateString) {
    if (!dateString) return "Sin fecha";
    const d = _toDate(dateString);
    if (isNaN(d)) return "Sin fecha";
    // Preferir Intl para meridiem y localización consistente
    try {
      return d.toLocaleDateString("es-ES", {
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    } catch (e) {
      if (hasDayjs) return dayjs(dateString).format("D [de] MMMM [de] YYYY");
      return d.toDateString();
    }
  }

  function formatShortDate(dateString) {
    if (!dateString) return "Sin fecha";
    const d = _toDate(dateString);
    if (isNaN(d)) return "Sin fecha";
    try {
      return d.toLocaleString("es-ES", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      });
    } catch (e) {
      if (hasDayjs) return dayjs(dateString).format("DD/MM/YYYY HH:mm");
      return `${d.getDate()}/${
        d.getMonth() + 1
      }/${d.getFullYear()} ${d.getHours()}:${String(d.getMinutes()).padStart(
        2,
        "0",
      )}`;
    }
  }

  function formatOnlyDate(dateString) {
    if (!dateString) return "Sin fecha";
    const d = _toDate(dateString);
    if (isNaN(d)) return "Sin fecha";
    try {
      return d.toLocaleDateString("es-ES", {
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    } catch (e) {
      if (hasDayjs) return dayjs(dateString).format("D [de] MMMM [de] YYYY");
      return d.toDateString();
    }
  }

  function formatDateTime(dateString) {
    if (!dateString) return "Sin fecha";
    const d = _toDate(dateString);
    if (isNaN(d)) return "Sin fecha";
    try {
      // hour12:true para formato 12h (ej: 8:00 a. m.) en español
      return d.toLocaleString("es-ES", {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      });
    } catch (e) {
      if (hasDayjs)
        return dayjs(dateString).format("D [de] MMMM [de] YYYY, h:mm A");
      return d.toLocaleString();
    }
  }

  function formatDateTimeForInput(dateTimeString) {
    if (!dateTimeString) return "";
    const d = _toDate(dateTimeString);
    if (isNaN(d)) return "";
    const pad = (n) => String(n).padStart(2, "0");
    const year = d.getFullYear();
    const month = pad(d.getMonth() + 1);
    const day = pad(d.getDate());
    const hours = pad(d.getHours());
    const minutes = pad(d.getMinutes());
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  }

  function formatTime(dateString) {
    if (!dateString) return "--:--";
    const d = _toDate(dateString);
    if (isNaN(d)) return "--:--";
    try {
      return d.toLocaleTimeString("es-ES", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      });
    } catch (e) {
      if (hasDayjs) return dayjs(dateString).format("HH:mm");
      return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
    }
  }

  const exported = {
    formatDate,
    formatShortDate,
    formatOnlyDate,
    formatDateTime,
    formatDateTimeForInput,
    formatTime,
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
