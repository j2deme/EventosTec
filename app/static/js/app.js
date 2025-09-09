// static/js/app.js
console.log("App JS loaded");

// Función para obtener token de autenticación
function getAuthToken() {
  return localStorage.getItem("authToken");
}

// Función para verificar si el usuario está autenticado (versión completa con verificación de expiración)
function isAuthenticated() {
  const token = getAuthToken();
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

// Función para obtener headers con autorización
function getAuthHeaders(additionalHeaders = {}) {
  const token = getAuthToken();
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
  // Guardar referencia al fetch original de forma segura
  const _fetch = window.fetch;

  // Reemplazar fetch con una versión que agrega el token automáticamente
  window.fetch = function (input, init = {}) {
    const token = getAuthToken();

    // Si hay token, agregarlo a los headers
    if (token) {
      init.headers = {
        ...init.headers,
        Authorization: `Bearer ${token}`,
      };
    }

    // Asegurar Content-Type si no existe y hay cuerpo
    if (init.body && !init.headers["Content-Type"]) {
      init.headers = {
        ...init.headers,
        "Content-Type": "application/json",
      };
    }

    // console.log("Fetch interceptado:", input, init); // Para debugging

    // Continuar con la solicitud original
    return _fetch(input, init);
  };

  //console.log("Interceptor de fetch instalado correctamente");
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
if (typeof dayjs !== "undefined") {
  dayjs.locale("es");

  function formatDate(dateString) {
    if (!dateString) return "Sin fecha";
    return dayjs(dateString).format("D [de] MMMM [de] YYYY [a las] H:mm");
  }

  function formatShortDate(dateString) {
    if (!dateString) return "Sin fecha";
    return dayjs(dateString).format("DD/MM/YYYY HH:mm");
  }

  function formatOnlyDate(dateString) {
    if (!dateString) return "Sin fecha";
    return dayjs(dateString).format("D [de] MMMM [de] YYYY");
  }

  // Hacer las funciones de fecha globalmente disponibles
  window.formatDate = formatDate;
  window.formatShortDate = formatShortDate;
  window.formatOnlyDate = formatOnlyDate;
}

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
