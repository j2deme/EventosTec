// static/js/app.js

// Función para obtener token de autenticación
function getAuthToken() {
  try {
    return localStorage.getItem("authToken");
  } catch (e) {
    return null;
  }
}

// Función para verificar si el usuario está autenticado (versión completa con verificación de expiración)
function isAuthenticated() {
  const token = localStorage.getItem("authToken");
  if (!token) return false;

  // Verificar si el token ha expirado
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    const isExpired = payload.exp <= Date.now() / 1000;
    if (isExpired) {
      // Si el token expiró, limpiar localStorage
      localStorage.removeItem("authToken");
      localStorage.removeItem("userType");
      return false;
    }
    return true;
  } catch (e) {
    // Si hay error al parsear, el token es inválido
    localStorage.removeItem("authToken");
    localStorage.removeItem("userType");
    return false;
  }
}

// Función para hacer logout
function logout() {
  if (confirm("¿Estás seguro de cerrar sesión?")) {
    localStorage.removeItem("authToken");
    localStorage.removeItem("userType");
    localStorage.removeItem("studentProfile");
    localStorage.removeItem("adminActiveTab");
    localStorage.removeItem("studentActiveTab");
    window.location.href = "/";
  }
}

// Hacer logout globalmente disponible
window.logout = logout;

// Exponer funciones de autenticación para tests y otros módulos
window.getAuthToken = getAuthToken;
window.isAuthenticated = isAuthenticated;

// Función para obtener headers con autorización
function getAuthHeaders(additionalHeaders = {}) {
  const token = localStorage.getItem("authToken");
  const baseHeaders = {
    "Content-Type": "application/json",
  };

  if (token) {
    return {
      ...baseHeaders,
      ...additionalHeaders,
      Authorization: `Bearer ${token}`,
    };
  }

  return {
    ...baseHeaders,
    ...additionalHeaders,
  };
}

// Hacer getAuthHeaders globalmente disponible
window.getAuthHeaders = getAuthHeaders;

// Función para obtener el tipo de usuario
function getUserType() {
  return localStorage.getItem("userType") || "student";
}

// Hacer getUserType globalmente disponible
window.getUserType = getUserType;

// Función para verificar autenticación en rutas protegidas
function checkAuth() {
  if (!isAuthenticated()) {
    // Solo redirigir si no estamos ya en la página de login
    if (window.location.pathname !== "/") {
      window.location.href = "/";
    }
    return false;
  }
  return true;
}

// ✨ INTERCEPTOR GLOBAL DE FETCH - Corregido y mejorado
(function setupFetchInterceptor() {
  // Capturar la referencia original a fetch (si existe) en el momento de carga.
  // Tests del repo mockean global.fetch *antes* de requerir este módulo, así
  // que conservar esta captura es importante.
  const _fetch = typeof window.fetch === "function" ? window.fetch : undefined;

  function mergeHeaders(init, extra) {
    const existing = (init && init.headers) || {};
    return {
      ...existing,
      ...extra,
    };
  }

  async function safeFetch(input, init = {}) {
    const token = getAuthToken();

    const finalInit = { ...(init || {}) };
    if (token) {
      finalInit.headers = mergeHeaders(finalInit, {
        Authorization: `Bearer ${token}`,
      });
    }

    if (finalInit.body && !finalInit.headers?.["Content-Type"]) {
      finalInit.headers = mergeHeaders(finalInit, {
        "Content-Type": "application/json",
      });
    }

    let response;

    // Prefer the originally captured `_fetch` reference for runtime safety
    // (prevents wrapper -> safeFetch -> wrapper recursion in the browser).
    if (typeof _fetch === "function") {
      response = await _fetch(input, finalInit);
    } else if (
      typeof globalThis.fetch === "function" &&
      globalThis.fetch !== wrapperFetch
    ) {
      response = await globalThis.fetch(input, finalInit);
    } else {
      throw new Error("fetch no está disponible en este entorno");
    }

    // Manejar automáticamente errores 401 (sesión expirada)
    if (response.status === 401) {
      showToast(
        "🔴 Tu sesión ha expirado. Serás redirigido al login.",
        "error"
      );
      setTimeout(() => checkAuthAndRedirect(), 1500);
    }

    return response;
  }

  // Wrapper function assigned to window.fetch. We keep a reference so safeFetch
  // can detect and avoid calling the wrapper recursively.
  function wrapperFetch(input, init) {
    return safeFetch(input, init);
  }

  window.fetch = wrapperFetch;

  // Exponer helper estable para que los módulos lo usen explícitamente
  window.safeFetch = safeFetch;

  // También exportar para entornos CommonJS (Jest)
  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      getAuthToken,
      isAuthenticated,
      getAuthHeaders,
      safeFetch,
      showToast,
    };
  }
})();

// Verificación de autenticación en rutas protegidas
(function checkProtectedRoutes() {
  document.addEventListener("DOMContentLoaded", () => {
    // Verificar autenticación en páginas protegidas
    const protectedRoutes = ["/dashboard/"];
    const currentPath = window.location.pathname;

    if (protectedRoutes.some((route) => currentPath.startsWith(route))) {
      if (!isAuthenticated()) {
        window.location.href = "/";
      }
    }
  });
})();

function checkAuthAndRedirect() {
  if (!isAuthenticated()) {
    window.location.href = "/";
    return false;
  }
  return true;
}

// Hacerla globalmente disponible
window.checkAuthAndRedirect = checkAuthAndRedirect;

// Simplify date helpers: expose `window.dateHelpers` as the canonical source
// for date formatting. Tests and modules that still call `window.format*`
// should be migrated to use `dateHelpers` directly or `window.dateHelpers`.
// We keep a minimal non-invasive fallback: if a module defined window.format*
// earlier, we do not overwrite them, but we won't reassign them here.
(function exposeCanonicalDateHelpers() {
  try {
    const dateHelpers = require("./helpers/dateHelpers");
    if (dateHelpers) {
      // Expose the canonical helpers object
      window.dateHelpers = dateHelpers;

      // Export for CommonJS consumers
      if (typeof module !== "undefined" && module.exports) {
        module.exports.dateHelpers = dateHelpers;
      }
      return;
    }
  } catch (e) {
    // Not CommonJS/runtime without require: do not overwrite existing window.format*
    // but ensure a minimal dateHelpers object exists so modules can call it.
  }

  window.dateHelpers = window.dateHelpers || {
    formatDate: window.formatDate,
    formatShortDate: window.formatShortDate,
    formatOnlyDate: window.formatOnlyDate,
    formatDateTime: window.formatDateTime,
    formatDateTimeForInput: window.formatDateTimeForInput,
    formatTime: window.formatTime,
  };
})();

// Backwards-compatible global date formatter functions.
// If a module already defines window.formatX, we don't overwrite it.
// Otherwise we delegate to window.dateHelpers.* and provide small
// sensible fallbacks used by tests.
(function exposeGlobalDateFunctions() {
  function delegate(name, fallback) {
    if (typeof window[name] === "function") return;
    window[name] = function (...args) {
      try {
        const dh = window.dateHelpers || {};
        if (typeof dh[name] === "function") return dh[name].apply(dh, args);
      } catch (e) {
        // ignore and fallback
      }
      // fallback value or fallback function
      if (typeof fallback === "function") return fallback.apply(null, args);
      return fallback;
    };
  }

  delegate("formatDate", function (d) {
    if (!d) return "Sin fecha";
    return String(d);
  });

  delegate("formatShortDate", function (d) {
    if (!d) return "Sin fecha";
    return String(d);
  });

  delegate("formatOnlyDate", function (d) {
    if (!d) return "Sin fecha";
    return String(d).split("T")[0] || String(d);
  });

  delegate("formatDateTime", function (d) {
    if (!d) return "Sin fecha";
    return String(d);
  });

  delegate("formatDateTimeForInput", function (d) {
    if (!d) return "";
    // Try to produce a YYYY-MM-DDTHH:MM fallback
    try {
      const dt = new Date(d);
      if (isNaN(dt.getTime())) return "";
      const pad = (n) => String(n).padStart(2, "0");
      const y = dt.getFullYear();
      const m = pad(dt.getMonth() + 1);
      const day = pad(dt.getDate());
      const hh = pad(dt.getHours());
      const mm = pad(dt.getMinutes());
      return `${y}-${m}-${day}T${hh}:${mm}`;
    } catch (e) {
      return "";
    }
  });

  delegate("formatTime", function (d) {
    if (!d) return "";
    try {
      const dt = new Date(d);
      if (isNaN(dt.getTime())) return "";
      const pad = (n) => String(n).padStart(2, "0");
      return `${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
    } catch (e) {
      return "";
    }
  });

  // Expose these on module.exports for CommonJS tests that require app.js
  if (typeof module !== "undefined" && module.exports) {
    module.exports.formatDate = window.formatDate;
    module.exports.formatShortDate = window.formatShortDate;
    module.exports.formatOnlyDate = window.formatOnlyDate;
    module.exports.formatDateTime = window.formatDateTime;
    module.exports.formatDateTimeForInput = window.formatDateTimeForInput;
    module.exports.formatTime = window.formatTime;
  }
})();

// Función para mostrar notificaciones con Toastify
function showToast(message, type = "success", duration = 3000) {
  // Verificar que Toastify esté disponible
  if (typeof Toastify === "undefined") {
    console.warn("Toastify no está disponible, mostrando alerta normal");
    alert(message);
    return;
  }

  let backgroundColor = "#10B981"; // Verde para éxito
  let className = "toast-success";

  switch (type) {
    case "error":
      backgroundColor = "#EF4444"; // Rojo para error
      className = "toast-error";
      break;
    case "warning":
      backgroundColor = "#F59E0B"; // Amarillo para advertencia
      className = "toast-warning";
      break;
    case "info":
      backgroundColor = "#3B82F6"; // Azul para información
      className = "toast-info";
      break;
    default:
      backgroundColor = "#10B981"; // Verde por defecto
  }

  Toastify({
    text: message,
    duration: duration,
    close: true,
    gravity: "top",
    position: "right",
    stopOnFocus: true,
    className: className,
    style: {
      background: backgroundColor,
      borderRadius: "0.5rem",
      padding: "1rem",
      fontFamily: "ui-sans-serif, system-ui, sans-serif",
      fontWeight: "500",
      fontSize: "0.875rem",
      lineHeight: "1.25rem",
    },
    onClick: function () {},
  }).showToast();
}

// Hacer la función globalmente disponible
window.showToast = showToast;

// Manager de estado de sesión JWT para indicador visual
function sessionStatusManager() {
  return {
    status: "checking", // 'active', 'warning', 'expired', 'checking'
    timeRemaining: null,
    warningThreshold: 5 * 60, // 5 minutos en segundos
    checkInterval: null,
    _warningShown: false,

    init() {
      this.checkStatus();
      // Verificar cada 30 segundos
      this.checkInterval = setInterval(() => this.checkStatus(), 30000);
    },

    destroy() {
      if (this.checkInterval) {
        clearInterval(this.checkInterval);
      }
    },

    checkStatus() {
      const token = getAuthToken();
      if (!token) {
        this.status = "expired";
        return;
      }

      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        const expTime = payload.exp;
        const now = Math.floor(Date.now() / 1000);
        const remaining = expTime - now;

        this.timeRemaining = remaining;

        if (remaining <= 0) {
          this.status = "expired";
          this.handleExpired();
        } else if (remaining <= this.warningThreshold) {
          this.status = "warning";
          this.handleWarning();
        } else {
          this.status = "active";
          // Reset warning flag when we're back to active
          this._warningShown = false;
        }
      } catch (e) {
        this.status = "expired";
        this.handleExpired();
      }
    },

    handleWarning() {
      // Mostrar toast de advertencia (una vez por ciclo)
      if (!this._warningShown) {
        showToast(
          `⚠️ Tu sesión expirará en ${Math.ceil(
            this.timeRemaining / 60
          )} minutos`,
          "warning",
          5000
        );
        this._warningShown = true;
      }
    },

    handleExpired() {
      showToast(
        "🔴 Tu sesión ha expirado. Serás redirigido al login.",
        "error"
      );
      setTimeout(() => checkAuthAndRedirect(), 2000);
    },

    getStatusClasses() {
      switch (this.status) {
        case "active":
          return "bg-green-400 ring-green-400";
        case "warning":
          return "bg-yellow-400 ring-yellow-400 animate-pulse";
        case "expired":
          return "bg-red-400 ring-red-400";
        default:
          return "bg-gray-400 ring-gray-400";
      }
    },

    getTooltip() {
      switch (this.status) {
        case "active":
          return `🟢 Sesión activa (${Math.ceil(
            this.timeRemaining / 60
          )} min restantes)`;
        case "warning":
          return `⚠️ Sesión expirando en ${Math.ceil(
            this.timeRemaining / 60
          )} minutos`;
        case "expired":
          return "🔴 Sesión expirada";
        default:
          return "⚡ Verificando estado de sesión...";
      }
    },
  };
}

// Hacer el manager globalmente disponible
window.sessionStatusManager = sessionStatusManager;
