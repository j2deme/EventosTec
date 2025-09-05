console.log("App JS loaded");

// Función para obtener token de autenticación
function getAuthToken() {
  return localStorage.getItem("authToken");
}

// Función para verificar si el usuario está autenticado
function isAuthenticated() {
  const token = getAuthToken();
  if (!token) return false;

  // Verificar si el token ha expirado
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.exp > Date.now() / 1000;
  } catch (e) {
    return false;
  }
}

// Función para hacer logout
function logout() {
  localStorage.removeItem("authToken");
  localStorage.removeItem("userType");
  window.location.href = "/";
}

// Función para verificar autenticación en rutas protegidas
function checkAuth() {
  if (!isAuthenticated()) {
    window.location.href = "/";
    return false;
  }
  return true;
}

// Interceptores para agregar token a las solicitudes
window.addEventListener("DOMContentLoaded", () => {
  // Verificar autenticación en páginas protegidas
  const protectedRoutes = ["/dashboard/"];
  const currentPath = window.location.pathname;

  if (protectedRoutes.some((route) => currentPath.startsWith(route))) {
    checkAuth();
  }
});

dayjs.locale("es");

// Función para formatear fechas
function formatDate(dateString) {
  if (!dateString) return "Sin fecha";
  // Day.js puede parsear muchos formatos de fecha
  return dayjs(dateString).format("D [de] MMMM [de] YYYY [a las] H:mm");
  // Ejemplo de salida: "15 de octubre de 2024 a las 14:30"
}

// O con hora más corta
function formatShortDate(dateString) {
  if (!dateString) return "Sin fecha";
  return dayjs(dateString).format("DD/MM/YYYY HH:mm");
  // Ejemplo de salida: "15/10/2024 14:30"
}

// O solo fecha
function formatOnlyDate(dateString) {
  if (!dateString) return "Sin fecha";
  return dayjs(dateString).format("D [de] MMMM [de] YYYY");
  // Ejemplo de salida: "15 de octubre de 2024"
}
