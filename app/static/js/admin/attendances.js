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
      only_without_registration: false,
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
            (a) =>
              String(a.event_id) === String(this.filters.event_id) ||
              String(a.event_id) === String(this.filters.event_id)
          )
        : this.activities.slice();

      if (this.filters.activity_type) {
        return byEvent.filter((a) => a.type === this.filters.activity_type);
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

      if (this.filters.only_without_registration) {
        rows = rows.filter((r) => !r.registration_id);
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

      return rows;
    },

    async init() {
      // Load basic lists used by filters
      await this.loadEvents();
      await this.loadActivities();
      // derive activityTypes from activities
      this.activityTypes = Array.from(
        new Set(this.activities.map((a) => a.type).filter(Boolean))
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
        if (this.filters.only_without_registration)
          qs.set("only_without_registration", "1");
        if (this.filters.activity_type)
          qs.set("activity_type", this.filters.activity_type);

        const url = "/api/attendances?" + qs.toString();
        const res = await this.sf(url, { method: "GET" });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));
        this.attendances = this.parseAttendancesPayload(body);
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

    async quickTogglePresent(row) {
      try {
        const res = await this.sf(`/api/attendances/${row.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mark_present: true }),
        });

        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          window.showToast &&
            window.showToast("Asistencia marcada como presente", "success");
          await this.refresh();

          this.dispatchAttendanceChanged({
            attendance_id: row.id,
            activity_id: row.activity_id,
            student_id: row.student_id,
          });
        } else {
          window.showToast &&
            window.showToast(
              body.message || "Error al actualizar asistencia",
              "error"
            );
        }
      } catch (err) {
        console.error(err);
        window.showToast && window.showToast("Error de conexión", "error");
      }
    },

    goToRegistration(row) {
      if (row.registration_id) {
        window.location.hash = `#registrations?id=${row.registration_id}`;
      }
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
