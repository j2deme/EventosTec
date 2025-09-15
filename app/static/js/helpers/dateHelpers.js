// helpers/dateHelpers.js
// Funciones de formateo de fecha centralizadas; usan dayjs si está disponible
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
  const d = new Date(dateTimeString);
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
  if (hasDayjs) return dayjs(dateString).format("HH:mm");
  const d = new Date(dateString);
  if (isNaN(d)) return "--:--";
  return d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
}

module.exports = {
  formatDate,
  formatShortDate,
  formatOnlyDate,
  formatDateTime,
  formatDateTimeForInput,
  formatTime,
};
