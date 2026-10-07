// helpers/registrationStatus.js
// ─────────────────────────────────────────────────────────────────────────────
// ÚNICA fuente del estado *visible* de un preregistro para el estudiante.
//
// El auto-registro (self check-in) NO cambia `registration.status`: solo
// marca `attended = True` y abre una sesión de asistencia ("Parcial"). El
// resultado final lo define el checkout del admin. Sin esto, el portal
// mostraba "Registrado"/"Confirmado" para siempre y el estudiante no podía
// saber si su asistencia quedó tomada.
//
// Reglas:
//   · Estado final (Asistió / Ausente / Cancelado) → manda `status`.
//   · Sesión abierta (`attendance.status === "Parcial"`, o `attended` como
//     fallback cuando la respuesta no trae `attendance`) →
//     "Asistencia registrada".
//   · En otro caso → `status` tal cual.
// ─────────────────────────────────────────────────────────────────────────────
(function () {
  if (
    typeof window !== "undefined" &&
    window.registrationStatus &&
    window.registrationStatus.__initialized
  ) {
    if (typeof module !== "undefined" && module.exports)
      module.exports = window.registrationStatus;
    return;
  }

  const FINAL_STATUSES = ["Asistió", "Ausente", "Cancelado"];
  const OPEN_LABEL = "Asistencia registrada";

  function isFinal(reg) {
    return !!(reg && reg.status && FINAL_STATUSES.indexOf(reg.status) !== -1);
  }

  // ¿La asistencia del estudiante quedó tomada y la sesión sigue abierta?
  function isOpen(reg) {
    if (!reg || isFinal(reg)) return false;

    const attendance = reg.attendance;
    if (attendance && attendance.status) {
      return attendance.status === "Parcial";
    }
    // Sin `attendance` en la respuesta: usar el flag que sí serializa el
    // schema de Registration.
    return !!reg.attended;
  }

  function checkInTime(reg) {
    const attendance = (reg && reg.attendance) || {};
    const value = attendance.check_in_time;
    if (!value) return "";

    try {
      if (
        window.dateHelpers &&
        typeof window.dateHelpers.formatTime === "function"
      ) {
        return window.dateHelpers.formatTime(value);
      }
    } catch (e) {
      // sin dateHelpers: fallback al slicing de abajo
    }
    const raw = String(value);
    return raw.length >= 16 ? raw.slice(11, 16) : "";
  }

  // Texto del badge del portal.
  function visibleStatus(reg) {
    if (!reg) return "Pre-registrado";
    if (isOpen(reg)) return OPEN_LABEL;
    return reg.status || "Pre-registrado";
  }

  // Nota aclaratoria bajo el badge; `null` cuando no aplica.
  function note(reg) {
    if (!isOpen(reg)) return null;
    const time = checkInTime(reg);
    return time
      ? `Tu entrada quedó registrada (${time}). El resultado final se define al cierre de la actividad.`
      : "Tu asistencia quedó registrada. El resultado final se define al cierre de la actividad.";
  }

  const exported = {
    isOpen,
    visibleStatus,
    note,
    checkInTime,
    OPEN_LABEL,
    __initialized: true,
  };

  // Export for CommonJS (tests) and expose in browser as window.registrationStatus
  if (typeof module !== "undefined" && module.exports) {
    module.exports = exported;
  }

  if (typeof window !== "undefined") {
    window.registrationStatus = window.registrationStatus || exported;
    window.registrationStatus.__initialized = true;
  }
})();
