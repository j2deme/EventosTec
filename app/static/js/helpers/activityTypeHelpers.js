// static/js/helpers/activityTypeHelpers.js
// ─────────────────────────────────────────────────────────────────────────────
// ÚNICA fuente de presentación por TIPO de actividad del frontend.
// La usan la vista de administrador (calendario y lista de actividades), la
// vista del estudiante y la vista pública de preregistros, para que todos los
// lugares muestren exactamente la misma paleta e iconografía.
//
// Paleta canónica (decisión de producto — colores de la vista del estudiante):
//   Magistral   → indigo  (color "main" de la plataforma)
//   Conferencia → yellow
//   Taller      → green
//   Curso       → blue
//   Otro        → gray    (neutral)
//
// Cada tipo expone:
//   border   → borde fuerte del chip/tarjeta (tono 600; "Otro" en 400)
//   soft     → círculo con el icono del tipo (fondo tono 100 + texto tono 700)
//   chip     → superficie del chip con texto (fondo tono 50 + texto tono 900)
//   tag      → píldora de tipo en tablas (fondo tono 100 + texto tono 800)
//   icon     → icono semántico Tabler del tipo (mismos que la vista pública)
//   iconFull → `ti <icono> text-<tono>-600` (icono suelto con su color)
//   label    → etiqueta a mostrar
//
// durationBetween(start, end) → duración POR SESIÓN ("2 h 30 min"). En
// actividades multisesión los datos traen el horario diario fijo, por lo que
// la resta entre hora de inicio y fin es la duración de esa sesión (no el
// total de la actividad, que vive en duration_hours).
//
// ⚠️ Las clases deben ser literales completas (nunca `bg-${color}-100`):
//    Tailwind CDN genera el CSS a partir de lo que aterriza en el DOM.
// ─────────────────────────────────────────────────────────────────────────────
(function () {
  if (
    typeof window !== "undefined" &&
    window.activityTypeHelpers &&
    window.activityTypeHelpers.__initialized
  ) {
    // Entorno CommonJS: exportamos la referencia existente (idempotente)
    if (typeof module !== "undefined" && module.exports) {
      module.exports = window.activityTypeHelpers;
    }
    return;
  }

  const TYPES = {
    Magistral: {
      label: "Magistral",
      icon: "ti-school",
      border: "border-indigo-600",
      soft: "bg-indigo-100 text-indigo-700",
      chip: "border-indigo-600 bg-indigo-50 text-indigo-900",
      tag: "bg-indigo-100 text-indigo-800",
      iconColor: "text-indigo-600",
    },
    Conferencia: {
      label: "Conferencia",
      icon: "ti-presentation",
      border: "border-yellow-600",
      soft: "bg-yellow-100 text-yellow-700",
      chip: "border-yellow-600 bg-yellow-50 text-yellow-900",
      tag: "bg-yellow-100 text-yellow-800",
      iconColor: "text-yellow-600",
    },
    Taller: {
      label: "Taller",
      icon: "ti-tools",
      border: "border-green-600",
      soft: "bg-green-100 text-green-700",
      chip: "border-green-600 bg-green-50 text-green-900",
      tag: "bg-green-100 text-green-800",
      iconColor: "text-green-600",
    },
    Curso: {
      label: "Curso",
      icon: "ti-device-laptop",
      border: "border-blue-600",
      soft: "bg-blue-100 text-blue-700",
      chip: "border-blue-600 bg-blue-50 text-blue-900",
      tag: "bg-blue-100 text-blue-800",
      iconColor: "text-blue-600",
    },
  };

  // Fallback: tipos fuera del enum (y valores nulos/undefined)
  const FALLBACK = {
    label: "Otro",
    icon: "ti-tag",
    border: "border-gray-400",
    soft: "bg-gray-100 text-gray-600",
    chip: "border-gray-400 bg-gray-50 text-gray-800",
    tag: "bg-gray-100 text-gray-800",
    iconColor: "text-gray-600",
  };

  function info(type) {
    return TYPES[type] || FALLBACK;
  }

  // Superficie del chip (borde fuerte + fondo suave + texto)
  function color(type) {
    return info(type).chip;
  }

  // Solo el borde fuerte (tarjeta del estudiante)
  function border(type) {
    return info(type).border;
  }

  // Círculo con el icono del tipo
  function soft(type) {
    return info(type).soft;
  }

  function icon(type) {
    return info(type).icon;
  }

  // Icono suelto con su color: "ti ti-school text-indigo-600"
  function iconFull(type) {
    const i = info(type);
    return `ti ${i.icon} ${i.iconColor}`;
  }

  // Píldora de tipo en tablas/listados: "bg-indigo-100 text-indigo-800"
  function tag(type) {
    return info(type).tag;
  }

  // Etiqueta visible: para tipos desconocidos se muestra "Otro"
  function label(type) {
    return info(type).label;
  }

  function keys() {
    return Object.keys(TYPES);
  }

  function has(type) {
    return Object.prototype.hasOwnProperty.call(TYPES, type);
  }

  // "09:00" | "2026-10-08 09:00:00" | Date → minutos locales del día
  function _toMinutes(value) {
    if (value === null || value === undefined || value === "") return null;
    if (value instanceof Date) {
      return isNaN(value.getTime())
        ? null
        : value.getHours() * 60 + value.getMinutes();
    }
    const s = String(value).trim();
    // Hora pura "HH:MM" o "HH:MM:SS" (no es un datetime, no hay que parsear)
    const hm = s.match(/^(\d{1,2}):(\d{2})(?::\d{2})?/);
    if (hm) {
      const h = parseInt(hm[1], 10);
      const m = parseInt(hm[2], 10);
      if (h > 23 || m > 59) return null;
      return h * 60 + m;
    }
    const d = new Date(s);
    if (isNaN(d.getTime())) return null;
    return d.getHours() * 60 + d.getMinutes();
  }

  // Duración legible ENTRE dos horas/inicios. Devuelve "" si falta algún dato.
  function durationBetween(start, end) {
    const a = _toMinutes(start);
    const b = _toMinutes(end);
    if (a === null || b === null) return "";
    let mins = b - a;
    // Sesión que cruza la medianoche (19:00 → 00:00 = 5 h)
    if (mins < 0) mins += 24 * 60;
    if (mins <= 0) return "";
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    if (h && m) return `${h} h ${m} min`;
    if (h) return `${h} h`;
    return `${m} min`;
  }

  const exported = {
    TYPES,
    FALLBACK,
    info,
    color,
    border,
    soft,
    icon,
    iconFull,
    tag,
    label,
    keys,
    has,
    durationBetween,
    __initialized: true,
  };

  // Export for CommonJS (tests) and expose in browser as window.activityTypeHelpers
  if (typeof module !== "undefined" && module.exports) {
    module.exports = exported;
  }

  if (typeof window !== "undefined") {
    // Do not overwrite an existing window.activityTypeHelpers (defensive)
    window.activityTypeHelpers = window.activityTypeHelpers || exported;
    window.activityTypeHelpers.__initialized = true;
  }
})();
