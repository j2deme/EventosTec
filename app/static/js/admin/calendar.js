// static/js/admin/calendar.js
// Vista calendario: distribución de actividades por día y horario de un evento.
function calendarAdmin() {
  return {
    // Estado
    loading: false,
    errorMessage: "",
    events: [],
    selectedEventId: null,
    calendar: null, // {event, days, activities, total_activities}
    showDetail: false,
    selectedActivity: null,

    // Inicialización
    async init() {
      this.showDetail = false;
      this.selectedActivity = null;

      // Lazy-init (Fase D): diferir la carga hasta la pestaña "calendar"
      await window.tabLazyBoot("calendar", () => this.loadEvents());
    },

    // Cargar lista de eventos (selector) y auto-seleccionar el primero
    async loadEvents() {
      this.loading = true;
      this.errorMessage = "";

      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(
          "/api/events/?page=1&per_page=100&sort=start_date:desc",
        );
        if (!response.ok) {
          throw new Error("Error al cargar los eventos");
        }
        const data = await response.json();
        this.events = (data && data.events) || [];

        if (this.events.length > 0) {
          this.selectedEventId = String(this.events[0].id);
          await this.loadCalendar(this.selectedEventId);
        }
      } catch (e) {
        this.errorMessage = (e && e.message) || "Error al cargar los eventos";
      } finally {
        this.loading = false;
      }
    },

    // Cambio de evento en el selector
    async onEventChange() {
      if (this.selectedEventId) {
        await this.loadCalendar(this.selectedEventId);
      }
    },

    // Cargar calendario del evento seleccionado
    async loadCalendar(eventId) {
      if (!eventId) return;
      this.loading = true;
      this.errorMessage = "";
      this.calendar = null;

      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(`/api/events/${eventId}/calendar`);
        if (!response.ok) {
          throw new Error("Error al cargar el calendario");
        }
        this.calendar = await response.json();
      } catch (e) {
        this.errorMessage =
          (e && e.message) || "Error al cargar el calendario";
      } finally {
        this.loading = false;
      }
    },

    // --- Helpers de vista ---

    // Actividades de un día, ordenadas por hora de inicio
    dayActivities(dayIso) {
      if (!this.calendar) return [];
      return (this.calendar.activities || [])
        .filter((a) => a.day === dayIso)
        .sort((a, b) =>
          (a.starts_at || "").localeCompare(b.starts_at || ""),
        );
    },

    // Actividades fuera de la ventana del evento (o sin fecha)
    outsideActivities() {
      if (!this.calendar) return [];
      const days = this.calendar.days || [];
      return (this.calendar.activities || []).filter(
        (a) => !a.day || days.indexOf(a.day) === -1,
      );
    },

    // Contador de actividades de un día (para el encabezado de la columna)
    dayCount(dayIso) {
      return this.dayActivities(dayIso).length;
    },

    // Etiqueta de día legible. Parseo manual de "YYYY-MM-DD" para evitar el
    // corrimiento de zona que produce new Date("YYYY-MM-DD") (UTC midnight).
    dayLabel(dayIso) {
      const parts = String(dayIso).split("-").map((n) => parseInt(n, 10));
      if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) {
        return String(dayIso);
      }
      const d = new Date(parts[0], parts[1] - 1, parts[2]);
      return d.toLocaleDateString("es-MX", {
        weekday: "short",
        day: "numeric",
        month: "short",
      });
    },

    // Color por tipo de actividad (tipos del enum del modelo)
    typeColor(type) {
      switch (type) {
        case "Magistral":
          return "border-rose-500 bg-rose-50 text-rose-900";
        case "Conferencia":
          return "border-indigo-500 bg-indigo-50 text-indigo-900";
        case "Taller":
          return "border-emerald-500 bg-emerald-50 text-emerald-900";
        case "Curso":
          return "border-amber-500 bg-amber-50 text-amber-900";
        default:
          return "border-slate-400 bg-slate-50 text-slate-800";
      }
    },

    // "registrados/cupo" — solo si hay cupo definido
    cupoLabel(activity) {
      if (!activity || activity.max_capacity == null) return "";
      return `${activity.registered_count || 0}/${activity.max_capacity}`;
    },

    // Columnas del grid: una por día del evento (el ancho depende del evento,
    // por eso style inline en lugar de clases dinámicas)
    gridStyle() {
      const n =
        (this.calendar && this.calendar.days && this.calendar.days.length) || 1;
      return `grid-template-columns: repeat(${Math.max(n, 1)}, minmax(200px, 1fr));`;
    },

    // Modal de detalle
    openDetail(activity) {
      this.selectedActivity = activity;
      this.showDetail = true;
    },
    closeDetail() {
      this.showDetail = false;
      this.selectedActivity = null;
    },
  };
}

// Exponer globalmente para Alpine (x-data="calendarAdmin()")
if (typeof window !== "undefined") {
  window.calendarAdmin = calendarAdmin;
}

// Exportar para Node/Jest (CommonJS)
if (typeof module !== "undefined" && module.exports) {
  module.exports = calendarAdmin;
}
