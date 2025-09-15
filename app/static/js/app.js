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

    // Prefer the originally captured `_fetch` reference for runtime safety
    // (prevents wrapper -> safeFetch -> wrapper recursion in the browser).
    if (typeof _fetch === "function") {
      return _fetch(input, finalInit);
    }

    // If `_fetch` is not available (uncommon in tests), try to use the
    // current global fetch only if it's a real function and not the
    // wrapperFetch we assign below. This restores some compatibility with
    // tests that mock `global.fetch` before or after requiring this module.
    if (
      typeof globalThis.fetch === "function" &&
      globalThis.fetch !== wrapperFetch
    ) {
      return globalThis.fetch(input, finalInit);
    }

    return Promise.reject(
      new Error("fetch no está disponible en este entorno")
    );
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

// Funciones para formatear fechas con dayjs
// Asegúrate de que dayjs esté cargado antes de usar estas funciones
// Exponer helpers de fecha globales.
// Usar dayjs si está disponible, si no caer en implementaciones basadas en Date.
(function exposeDateHelpers() {
  const hasDayjs = typeof dayjs !== "undefined";
  if (hasDayjs) dayjs.locale("es");

  function formatDate(dateString) {
    if (!dateString) return "Sin fecha";
    if (hasDayjs)
      return dayjs(dateString).format("D [de] MMMM [de] YYYY [a las] H:mm");
    const date = new Date(dateString);
    return date.toLocaleDateString("es-ES", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  function formatShortDate(dateString) {
    if (!dateString) return "Sin fecha";
    if (hasDayjs) return dayjs(dateString).format("DD/MM/YYYY HH:mm");
    const date = new Date(dateString);
    const d = String(date.getDate()).padStart(2, "0");
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const hh = String(date.getHours()).padStart(2, "0");
    const mm = String(date.getMinutes()).padStart(2, "0");
    return `${d}/${m}/${date.getFullYear()} ${hh}:${mm}`;
  }

  function formatOnlyDate(dateString) {
    if (!dateString) return "Sin fecha";
    if (hasDayjs) return dayjs(dateString).format("D [de] MMMM [de] YYYY");
    const date = new Date(dateString);
    return date.toLocaleDateString("es-ES", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  }

  function formatDateTime(dateString) {
    if (!dateString) return "Sin fecha";
    if (hasDayjs)
      return dayjs(dateString).format("D [de] MMMM [de] YYYY [a las] H:mm");
    const date = new Date(dateString);
    return date.toLocaleString("es-ES", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatDateTimeForInput(dateTimeString) {
    if (!dateTimeString) return "";
    const date = new Date(dateTimeString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  }

  // Exponer en window para que los módulos puedan delegar en estas funciones.
  window.formatDate = formatDate;
  window.formatShortDate = formatShortDate;
  window.formatOnlyDate = formatOnlyDate;
  window.formatDateTime = formatDateTime;
  window.formatDateTimeForInput = formatDateTimeForInput;
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
