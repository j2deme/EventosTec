// app/static/js/admin/reports.js
function reportsManager() {
  return {
    events: [],
    activities: [],
    activitiesFiltered: [],
    filters: {
      event_id: "",
      activity_id: "",
      department: "",
    },
    loading: false,
    matrix: null,
    matrix_semester: {},
    rowSubtotals: {},
    totalSumSemesters: 0,
    careers: [],
    generations: [],
    semesters: [],

    // Hours compliance report
    hoursFilters: {
      event_id: "",
      career: "",
      search: "",
      min_hours: 0,
      filter_10_plus: false,
    },
    hoursLoading: false,
    hoursStudents: [],
    uniqueCareers: [],
    showParticipationModal: false,
    currentStudent: null,
    participationDetails: [],
    participationDetailsLoading: false,
    totalParticipationHours: 0,

    init() {
      this.loadEvents();
      this.loadActivities();
      this.loadCareers();
    },

    departments: [],

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
          // derive departments list
          const deps = new Set();
          for (const a of this.activities)
            if (a.department) deps.add(a.department);
          this.departments = Array.from(deps).sort((x, y) =>
            x.localeCompare(y, undefined, { sensitivity: "base" })
          );
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
        if (this.filters.department)
          params.set("department", this.filters.department.toString().trim());
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

    // New: generate fill report
    fillReport: [],
    fillLoading: false,

    async generateFillReport() {
      this.fillLoading = true;
      this.fillReport = [];
      try {
        const params = new URLSearchParams();
        if (this.filters.event_id)
          params.set("event_id", this.filters.event_id);
        if (this.filters.activity_id)
          params.set("activity_id", this.filters.activity_id);
        if (this.filters.department)
          params.set("department", this.filters.department.toString().trim());
        // include_unlimited optional: include activities without capacity
        params.set("include_unlimited", "1");

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f(`/api/reports/activity_fill?${params.toString()}`);
        if (res && res.ok) {
          const d = await res.json();
          let activities = Array.isArray(d.activities) ? d.activities : [];

          // Normalize each activity: ensure percent is numeric, add labels and badge classes
          const STATUS_MAP = {
            available: {
              label: "Disponible",
              badge: "bg-amber-100 text-amber-800",
            },
            unlimited: { label: "Abierto", badge: "bg-blue-100 text-blue-800" },
            empty: { label: "Vacío", badge: "bg-red-100 text-red-800" },
            full: { label: "Lleno", badge: "bg-green-100 text-green-800" },
          };

          activities = activities.map((a) => {
            const percent =
              a.percent == null ? null : Math.round(Number(a.percent) || 0);
            const rawStatus = (a.status || "").toString().toLowerCase();
            const mapped = STATUS_MAP[rawStatus] || {
              label: a.status || "",
              badge: "bg-gray-100 text-gray-800",
            };
            return Object.assign({}, a, {
              percent,
              status_label: mapped.label,
              status_badge_class: mapped.badge,
            });
          });

          // Sort: 1) percent desc (nulls last), 2) name A-Z
          activities.sort((x, y) => {
            const px = x.percent == null ? -1 : x.percent;
            const py = y.percent == null ? -1 : y.percent;
            if (py !== px) return py - px; // desc
            const nx = (x.name || "").toString();
            const ny = (y.name || "").toString();
            return nx.localeCompare(ny, undefined, { sensitivity: "base" });
          });

          this.fillReport = activities;
        } else {
          const err = await res.json().catch(() => ({}));
          window.showToast &&
            window.showToast(
              err.message || "Error generando reporte de llenado",
              "error"
            );
        }
      } catch (e) {
        console.error("Error generating fill report", e);
        window.showToast &&
          window.showToast("Error generando reporte de llenado", "error");
      } finally {
        this.fillLoading = false;
      }
    },

    async downloadRegistrationsTxt() {
      try {
        if (!this.filters.event_id) {
          window.showToast &&
            window.showToast("Selecciona un evento primero", "error");
          return;
        }
        const params = new URLSearchParams();
        params.set("event_id", this.filters.event_id);
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f(
          `/api/reports/event_registrations_txt?${params.toString()}`
        );
        if (!res) return;
        if (res.ok) {
          const blob = await res.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          // El filename vendrá por header Content-Disposition; intentar extraerlo
          const cd = res.headers.get("Content-Disposition") || "";
          const m = cd.match(/filename="?(.*?)"?$/);
          const filename = m && m[1] ? m[1] : `registrations_${Date.now()}.txt`;
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(url);
        } else {
          const err = await res.json().catch(() => ({}));
          window.showToast &&
            window.showToast(
              err.message || "Error descargando archivo",
              "error"
            );
        }
      } catch (e) {
        console.error("Error downloading registrations txt", e);
        window.showToast &&
          window.showToast("Error descargando archivo", "error");
      }
    },

    // Hours compliance methods
    async loadCareers() {
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f("/api/students?per_page=1000");
        if (res && res.ok) {
          const d = await res.json();
          const students = d.students || [];
          const careerSet = new Set();
          students.forEach((s) => {
            if (s.career) careerSet.add(s.career);
          });
          this.uniqueCareers = Array.from(careerSet).sort();
        }
      } catch (e) {
        console.error("Error loading careers", e);
      }
    },

    onHoursEventChange() {
      // Reset other filters when event changes
      this.hoursFilters.career = "";
      this.hoursFilters.search = "";
      this.hoursStudents = [];
    },

    apply10PlusFilter() {
      if (this.hoursFilters.filter_10_plus) {
        this.hoursFilters.min_hours = 10;
      } else {
        this.hoursFilters.min_hours = 0;
      }
    },

    async generateHoursReport() {
      if (!this.hoursFilters.event_id) {
        window.showToast &&
          window.showToast("Selecciona un evento primero", "error");
        return;
      }

      this.hoursLoading = true;
      this.hoursStudents = [];
      try {
        const params = new URLSearchParams();
        params.set("event_id", this.hoursFilters.event_id);
        if (this.hoursFilters.career)
          params.set("career", this.hoursFilters.career);
        if (this.hoursFilters.search)
          params.set("search", this.hoursFilters.search);
        params.set("min_hours", this.hoursFilters.min_hours || 0);

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f(
          `/api/reports/hours_compliance?${params.toString()}`
        );
        if (res && res.ok) {
          const d = await res.json();
          this.hoursStudents = d.students || [];
          if (this.hoursStudents.length === 0) {
            window.showToast &&
              window.showToast(
                "No se encontraron estudiantes con los filtros seleccionados",
                "info"
              );
          }
        } else {
          const err = await res.json().catch(() => ({}));
          window.showToast &&
            window.showToast(
              err.message || "Error generando reporte de horas",
              "error"
            );
        }
      } catch (e) {
        console.error("Error generating hours report", e);
        window.showToast &&
          window.showToast("Error generando reporte de horas", "error");
      } finally {
        this.hoursLoading = false;
      }
    },

    async downloadHoursExcel() {
      if (!this.hoursFilters.event_id) {
        window.showToast &&
          window.showToast("Selecciona un evento primero", "error");
        return;
      }

      try {
        const params = new URLSearchParams();
        params.set("event_id", this.hoursFilters.event_id);
        if (this.hoursFilters.career)
          params.set("career", this.hoursFilters.career);
        if (this.hoursFilters.search)
          params.set("search", this.hoursFilters.search);
        params.set("min_hours", this.hoursFilters.min_hours || 0);

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f(
          `/api/reports/hours_compliance_excel?${params.toString()}`
        );
        if (!res) return;
        if (res.ok) {
          const blob = await res.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          const cd = res.headers.get("Content-Disposition") || "";
          const m = cd.match(/filename="?(.*?)"?$/);
          const filename =
            m && m[1] ? m[1] : `hours_compliance_${Date.now()}.xlsx`;
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(url);
        } else {
          const err = await res.json().catch(() => ({}));
          window.showToast &&
            window.showToast(
              err.message || "Error descargando archivo Excel",
              "error"
            );
        }
      } catch (e) {
        console.error("Error downloading hours excel", e);
        window.showToast &&
          window.showToast("Error descargando archivo Excel", "error");
      }
    },

    async viewParticipationDetails(studentId) {
      if (!this.hoursFilters.event_id) {
        return;
      }

      this.showParticipationModal = true;
      this.participationDetailsLoading = true;
      this.participationDetails = [];
      this.totalParticipationHours = 0;

      // Find student info
      const student = this.hoursStudents.find((s) => s.id === studentId);
      if (student) {
        this.currentStudent = student;
      }

      try {
        const params = new URLSearchParams();
        params.set("event_id", this.hoursFilters.event_id);

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f(
          `/api/reports/student_participations/${studentId}?${params.toString()}`
        );
        if (res && res.ok) {
          const d = await res.json();
          this.participationDetails = d.participations || [];
          this.totalParticipationHours = this.participationDetails.reduce(
            (sum, p) => sum + (p.duration_hours || 0),
            0
          );
        } else {
          const err = await res.json().catch(() => ({}));
          window.showToast &&
            window.showToast(
              err.message || "Error obteniendo participaciones",
              "error"
            );
        }
      } catch (e) {
        console.error("Error getting participation details", e);
        window.showToast &&
          window.showToast("Error obteniendo participaciones", "error");
      } finally {
        this.participationDetailsLoading = false;
      }
    },

    formatDateTime(isoString) {
      if (!isoString) return "";
      try {
        const date = new Date(isoString);
        return date.toLocaleString("es-MX", {
          year: "numeric",
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        });
      } catch (e) {
        return isoString;
      }
    },
  };
}

if (typeof window !== "undefined") window.reportsManager = reportsManager;
if (typeof module !== "undefined" && module.exports)
  module.exports = reportsManager;
