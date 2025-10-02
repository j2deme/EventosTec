// app/static/js/admin/reports.js
function reportsManager() {
  return {
    events: [],
    activities: [],
    activitiesFiltered: [],
    filters: {
      event_id: "",
      activity_id: "",
    },
    loading: false,
    matrix: null,
    matrix_semester: {},
    rowSubtotals: {},
    totalSumSemesters: 0,
    careers: [],
    generations: [],
    semesters: [],

    init() {
      this.loadEvents();
      this.loadActivities();
    },

    formatSemester(sem) {
      // Si es número o string numérico, devolver con 'o' (1 -> 1o). Mantener valores no numéricos.
      if (sem === null || sem === undefined) return "";
      const n = Number(sem);
      if (!Number.isNaN(n)) return `${n}o`;
      return String(sem);
    },

    async loadEvents() {
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f("/api/events?per_page=1000");
        if (res && res.ok) {
          const d = await res.json();
          this.events = d.events || [];
        }
      } catch (e) {
        console.error("Error loading events", e);
      }
    },

    async loadActivities() {
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f("/api/activities?per_page=1000");
        if (res && res.ok) {
          const d = await res.json();
          this.activities = d.activities || [];
          this.filterActivities();
        }
      } catch (e) {
        console.error("Error loading activities", e);
      }
    },

    filterActivities() {
      if (!this.filters.event_id) {
        this.activitiesFiltered = this.activities.slice();
        return;
      }
      this.activitiesFiltered = this.activities.filter(
        (a) =>
          String(a.event?.id || a.event_id || a.event?.id) ===
          String(this.filters.event_id)
      );
    },

    onEventChange() {
      this.filters.activity_id = "";
      this.filterActivities();
    },

    async generateMatrix() {
      this.loading = true;
      this.matrix = null;
      try {
        const params = new URLSearchParams();
        if (this.filters.event_id)
          params.set("event_id", this.filters.event_id);
        if (this.filters.activity_id)
          params.set("activity_id", this.filters.activity_id);

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f(
          `/api/reports/participation_matrix?${params.toString()}`
        );
        if (res && res.ok) {
          const d = await res.json();
          this.careers = Array.isArray(d.careers) ? d.careers : [];
          this.generations = Array.isArray(d.generations) ? d.generations : [];
          this.matrix = d.matrix || {};
          // Nuevo: datos por semestre (compatibilidad hacia atrás)
          this.semesters = Array.isArray(d.semesters) ? d.semesters : [];
          this.matrix_semester = d.matrix_semester || {};

          // Calcular subtotales por carrera y total general para exponer en el template
          // Forzar valores primitivos (Number) para evitar problemas con Proxies/reactividad
          const computedRowSubtotals = {};
          let computedTotal = 0;
          if (this.semesters.length && this.careers && this.careers.length) {
            for (const career of this.careers) {
              const key = String(career);
              let subtotal = 0;
              for (const s of this.semesters) {
                const raw = this.matrix_semester?.[key]?.[s];
                const val = typeof raw === "number" ? raw : Number(raw) || 0;
                subtotal += val;
              }
              // asegurar número primitivo
              computedRowSubtotals[key] = subtotal;
              computedTotal += subtotal;
            }
          }

          // Asignar en bloque (mejor para reactividad y evita Proxies en los valores)
          this.rowSubtotals = computedRowSubtotals;
          this.totalSumSemesters = computedTotal;
        } else {
          const err = await res.json().catch(() => ({}));
          window.showToast &&
            window.showToast(err.message || "Error generando matriz", "error");
        }
      } catch (e) {
        console.error("Error generating matrix", e);
        window.showToast && window.showToast("Error generando matriz", "error");
      } finally {
        this.loading = false;
      }
    },
  };
}

if (typeof window !== "undefined") window.reportsManager = reportsManager;
if (typeof module !== "undefined" && module.exports)
  module.exports = reportsManager;
