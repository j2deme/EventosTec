// attendances.js - Alpine component for admin quick-register
// Exports window.attendancesAdmin

// Top-level helper to dispatch a standardized `attendance:changed` event.
function dispatchAttendanceChangedEvent(detail) {
  try {
    if (typeof window === "undefined") return;
    try {
      window.dispatchEvent(new CustomEvent("attendance:changed", { detail }));
    } catch (e) {
      try {
        window.dispatchEvent(new Event("attendance:changed"));
      } catch (_) {
        // swallow - non-DOM or restricted env
      }
    }
  } catch (e) {
    // ignore
  }
}

function attendancesAdmin() {
  return {
    // State
    events: [],
    activities: [],
    activityTypes: [],
    attendances: [],
    loading: false,
    filters: {
      search: "",
      activity_id: "",
      event_id: "",
      // estado de filtro: 'all' | 'walkins' | 'registered'
      status_filter: "all",
      activity_type: "",
    },

    // Stats for dashboard cards
    statsToday: 0,
    statsWalkins: 0,
    statsConverted: 0,
    statsErrors: 0,

    // Modal state
    showModal: false,
    modalStudentId: "",
    modalActivityId: "",
    modalMarkPresent: false,
    // Registration view modal
    showRegistrationModal: false,
    registrationModalData: null,
    // Internal helpers to reduce duplication
    sf(url, opts) {
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      return f(url, opts);
    },

    parseAttendancesPayload(payload) {
      if (!payload) return [];
      if (Array.isArray(payload)) return payload;
      return payload.attendances || payload.data || [];
    },

    // Return activities filtered by selected event and activity_type
    filteredActivities() {
      const byEvent = this.filters.event_id
        ? this.activities.filter(
            (a) => String(a.event_id) === String(this.filters.event_id)
          )
        : this.activities.slice();

      if (this.filters.activity_type) {
        // activities coming from API use `activity_type` key
        return byEvent.filter(
          (a) => (a.activity_type || a.type) === this.filters.activity_type
        );
      }
      return byEvent;
    },

    // Return attendances filtered by search, activity and status
    attendancesTableFiltered() {
      let rows = this.attendances.slice();

      if (this.filters.activity_id) {
        rows = rows.filter(
          (r) => String(r.activity_id) === String(this.filters.activity_id)
        );
      }

      // status_filter puede ser 'all', 'walkins' (sin registro) o 'registered' (con registro)
      // Mantener compatibilidad con el antiguo flag `only_without_registration` usado en tests
      const wantsOnlyWithout =
        this.filters.status_filter === "walkins" ||
        this.filters.only_without_registration === true;
      if (wantsOnlyWithout) {
        rows = rows.filter((r) => !r.registration_id);
      } else if (this.filters.status_filter === "registered") {
        rows = rows.filter((r) => !!r.registration_id);
      }

      if (this.filters.activity_type) {
        rows = rows.filter(
          (r) => r.activity_type === this.filters.activity_type
        );
      }

      if (this.filters.search) {
        const q = String(this.filters.search).toLowerCase();
        rows = rows.filter((r) => {
          return (
            String(r.student_name || "")
              .toLowerCase()
              .includes(q) ||
            String(r.student_identifier || "")
              .toLowerCase()
              .includes(q) ||
            String(r.activity_name || "")
              .toLowerCase()
              .includes(q)
          );
        });
      }

      // Add unique key for Alpine.js x-for
      return rows.map((row, index) => ({
        ...row,
        key: row.id || `row-${index}`,
      }));
    },

    // Normalizar campos que la plantilla espera: status tokens, statusLabel, date_display, activity_type
    normalizeAttendances() {
      const statusMap = {
        Asistió: "present",
        Parcial: "registered",
        Registrado: "registered",
        Confirmado: "registered",
        Ausente: "error",
        // admitir tokens en inglés por si vienen así
        present: "present",
        registered: "registered",
        error: "error",
      };

      this.attendances = (this.attendances || []).map((att) => {
        const a = Object.assign({}, att);

        // activity_type may be nested under a.activity.activity_type or activity_type
        if (!a.activity_type) {
          a.activity_type =
            (a.activity && (a.activity.activity_type || a.activity.type)) ||
            a.activity_type ||
            "";
        }

        // Normalize status token and label
        const rawStatus = a.status || "";
        a.status = statusMap[rawStatus] || statusMap[String(rawStatus)] || null;
        a.statusLabel =
          rawStatus ||
          (a.status === "present"
            ? "Asistió"
            : a.status === "registered"
            ? "Parcial"
            : a.status === "error"
            ? "Ausente"
            : "");

        // date_display: usar created_at si existe, formatear simple YYYY-MM-DD HH:mm
        const created = a.created_at || a.createdAt || a.date || null;
        if (created) {
          try {
            const d = new Date(created);
            if (!isNaN(d)) {
              const pad = (n) => String(n).padStart(2, "0");
              const y = d.getFullYear();
              const m = pad(d.getMonth() + 1);
              const day = pad(d.getDate());
              const hh = pad(d.getHours());
              const mm = pad(d.getMinutes());
              a.date_display = `${y}-${m}-${day} ${hh}:${mm}`;
            } else {
              a.date_display = String(created);
            }
          } catch (e) {
            a.date_display = String(created);
          }
        } else {
          a.date_display = "—";
        }

        return a;
      });
    },

    calculateStats() {
      // statsToday: número de asistencias creadas hoy
      const today = new Date();
      const isSameDay = (d1, d2) =>
        d1.getFullYear() === d2.getFullYear() &&
        d1.getMonth() === d2.getMonth() &&
        d1.getDate() === d2.getDate();

      this.statsToday = (this.attendances || []).filter((att) => {
        if (!att.created_at) return false;
        const d = new Date(att.created_at);
        if (isNaN(d)) return false;
        return isSameDay(d, today);
      }).length;

      // Walk-ins: sin registration_id
      this.statsWalkins = (this.attendances || []).filter(
        (att) => !att.registration_id
      ).length;

      // Converted: con registration_id y status present
      this.statsConverted = (this.attendances || []).filter(
        (att) =>
          att.registration_id &&
          (att.status === "present" || att.status === "registered")
      ).length;

      // Errors: marcar como aquellas con status 'error' o attendance_percentage < 50
      this.statsErrors = (this.attendances || []).filter(
        (att) =>
          att.status === "error" ||
          (typeof att.attendance_percentage === "number" &&
            att.attendance_percentage < 50)
      ).length;
    },

    async init() {
      // Load basic lists used by filters
      await this.loadEvents();
      await this.loadActivities();
      // derive activityTypes from activities (API uses `activity_type`)
      this.activityTypes = Array.from(
        new Set(
          this.activities.map((a) => a.activity_type || a.type).filter(Boolean)
        )
      );
      // initial refresh of attendances
      await this.refresh();
    },

    async refresh() {
      this.loading = true;
      try {
        // load attendances with current filters (server-side support optional)
        const qs = new URLSearchParams();
        if (this.filters.search) qs.set("search", this.filters.search);
        if (this.filters.activity_id)
          qs.set("activity_id", this.filters.activity_id);
        if (this.filters.event_id) qs.set("event_id", this.filters.event_id);
        // Solo enviar parámetro al backend para walk-ins (compatibilidad histórica)
        if (this.filters.status_filter === "walkins")
          qs.set("only_without_registration", "1");
        if (this.filters.activity_type)
          qs.set("activity_type", this.filters.activity_type);

        const url = "/api/attendances?" + qs.toString();
        const res = await this.sf(url, { method: "GET" });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));
        this.attendances = this.parseAttendancesPayload(body);

        // Normalizar datos para la plantilla (status tokens, date_display, activity_type)
        this.normalizeAttendances();

        // Calcular stats después de normalizar
        this.calculateStats();
      } catch (err) {
        console.error(err);
      } finally {
        this.loading = false;
      }
    },

    async loadEvents() {
      try {
        const res = await this.sf("/api/events?per_page=100", {
          method: "GET",
        });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));
        this.events = body.data || body.events || [];
      } catch (e) {
        this.events = [];
      }
    },

    async loadActivities() {
      try {
        const res = await this.sf("/api/activities?per_page=500", {
          method: "GET",
        });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));
        this.activities = body.data || body.activities || [];
      } catch (e) {
        this.activities = [];
      }
    },

    async submitAssign() {
      if (!this.selectedActivity || !this.selectedStudent) return;
      const payload = {
        activity_id: this.selectedActivity,
        student_id: this.selectedStudent.id,
      };
      if (this.existingAttendance.mark_present) payload.mark_present = true;
      if (this.existingAttendance.check_in_time_input)
        payload.check_in_time = this.existingAttendance.check_in_time_input;
      if (this.existingAttendance.check_out_time_input)
        payload.check_out_time = this.existingAttendance.check_out_time_input;

      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f("/api/attendances/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          const assignedDefault = "Asistencia asignada correctamente.";
          const bodyMsg =
            body && typeof body.message === "string" ? body.message : "";
          const finalMessage =
            bodyMsg && bodyMsg !== "ok" ? bodyMsg : assignedDefault;

          if (res.status === 201) {
            window.showToast(
              body.message || "Asistencia creada correctamente.",
              "success"
            );
          } else if (res.status === 200) {
            window.showToast(
              body.message || "Asistencia actualizada correctamente.",
              "success"
            );
          } else {
            window.showToast(
              body.message || "Operaci\u00f3n completada.",
              "info"
            );
          }

          const dispatchedStudentId = this.selectedStudent?.id;
          this.message = finalMessage;
          this.selectedStudent = null;
          await this.loadExistingAttendance();

          // Notify other modules about the attendance change
          this.dispatchAttendanceChanged({
            activity_id: this.selectedActivity,
            student_id: dispatchedStudentId,
          });
        } else {
          window.showToast(
            body.message || "Error al asignar asistencia.",
            "error"
          );
        }
      } catch (err) {
        console.error(err);
        window.showToast(
          "Error de conexi\u00f3n al asignar asistencia.",
          "error"
        );
      }
    },

    // Modal methods
    openRegister() {
      this.showModal = true;
      this.modalStudentId = "";
      this.modalActivityId = "";
      this.modalMarkPresent = false;
    },

    closeModal() {
      this.showModal = false;
    },

    async submitModal() {
      if (!this.modalStudentId || !this.modalActivityId) {
        window.showToast &&
          window.showToast("Por favor completa todos los campos", "error");
        return;
      }

      try {
        const payload = {
          student_id: this.modalStudentId,
          activity_id: this.modalActivityId,
          mark_present: this.modalMarkPresent,
        };

        const res = await this.sf("/api/attendances/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          window.showToast &&
            window.showToast(
              body.message || "Asistencia registrada correctamente",
              "success"
            );
          this.closeModal();
          await this.refresh();

          // Dispatch attendance change event
          this.dispatchAttendanceChanged({
            activity_id: this.modalActivityId,
            student_id: this.modalStudentId,
          });
        } else {
          window.showToast &&
            window.showToast(
              body.message || "Error al registrar asistencia",
              "error"
            );
        }
      } catch (err) {
        console.error(err);
        window.showToast && window.showToast("Error de conexión", "error");
      }
    },

    // Action methods referenced in template
    openEditor(row) {
      console.log("Edit attendance:", row);
      // TODO: implement edit modal
    },

    // quickTogglePresent eliminado: acción redundante en este módulo

    goToRegistration(row) {
      // Open in-modal view when possible
      this.openRegistrationModal(row);
    },

    async openRegistrationModal(row) {
      // Prefer registration object included in the row
      if (!row) return;
      try {
        if (row.registration) {
          this.registrationModalData = row.registration;
        } else if (row.registration_id) {
          const res = await this.sf(
            `/api/registrations/${row.registration_id}`,
            {
              method: "GET",
            }
          );
          if (res && res.ok) {
            const body = await res.json().catch(() => ({}));
            this.registrationModalData =
              body.data || body.registration || body || null;
          } else {
            this.registrationModalData = null;
          }
        } else {
          this.registrationModalData = null;
        }
      } catch (e) {
        console.error(e);
        this.registrationModalData = null;
      }
      this.showRegistrationModal = true;
    },

    closeRegistrationModal() {
      this.showRegistrationModal = false;
      this.registrationModalData = null;
    },

    async deleteAttendance(row) {
      if (!confirm("¿Estás seguro de eliminar esta asistencia?")) return;

      try {
        const res = await this.sf(`/api/attendances/${row.id}`, {
          method: "DELETE",
        });

        if (res.ok) {
          window.showToast &&
            window.showToast("Asistencia eliminada", "success");
          await this.refresh();

          this.dispatchAttendanceChanged({
            attendance_id: row.id,
            activity_id: row.activity_id,
            student_id: row.student_id,
          });
        } else {
          const body = await res.json().catch(() => ({}));
          window.showToast &&
            window.showToast(
              body.message || "Error al eliminar asistencia",
              "error"
            );
        }
      } catch (err) {
        console.error(err);
        window.showToast && window.showToast("Error de conexión", "error");
      }
    },

    // Helper to add dispatch method for backward compatibility
    dispatchAttendanceChanged(detail) {
      dispatchAttendanceChangedEvent(detail);
    },
  };
}

try {
  if (typeof window !== "undefined") window.attendancesAdmin = attendancesAdmin;
} catch (e) {}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { attendancesAdmin };
  try {
    module.exports.default = module.exports;
  } catch (e) {}
}
