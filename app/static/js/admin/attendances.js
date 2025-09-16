// attendances.js - Alpine component for admin quick-register
// Exports window.attendancesAdmin

function attendancesAdmin() {
  return {
    attendancesTable: [],
    // Estadísticas para la cabecera (presentadas en la plantilla)
    statsToday: 0,
    statsWalkins: 0,
    statsConverted: 0,
    statsErrors: 0,
    filters: {
      search: "",
      event_id: "",
      activity_id: "",
      only_without_registration: false,
    },
    activities: [],
    loading: false,
    query: "",
    activityId: "",
    students: [],
    modalStudentName: "",
    modalActivityName: "",
    showModal: false,
    modalStudentId: "",
    modalActivityId: "",
    modalMarkPresent: true,
    modalMode: "create",
    modalExistingStatus: "",
    modalAttendancePercentage: 0,

    init() {
      this.loadActivities();
      this.refresh();
      try {
        window.addEventListener("open-assign-modal", () => {
          const c = document.getElementById("attendances-assign-container");
          if (c) c.style.display = "";
        });
        window.addEventListener("open-list-tab", () => {
          const c = document.getElementById("attendances-list-container");
          if (c) c.style.display = "";
        });
      } catch (e) {
        // ignore in non-DOM test environments
      }
    },

    async loadActivities() {
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f("/api/activities");
        if (!res.ok) throw new Error("No se pudieron cargar actividades");
        const data = await res.json();
        this.activities = Array.isArray(data) ? data : data.activities || [];
      } catch (err) {
        console.error(err);
        if (typeof showToast === "function")
          showToast("Error al cargar actividades", "error");
      }
    },

    async refresh() {
      this.loading = true;
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        // Solo recuperar attendances: ya no necesitamos preregistros
        const attResp = await f("/api/attendances?today=true&per_page=1000");
        let attendances = [];
        if (attResp && attResp.ok) {
          const attData = await attResp.json().catch(() => ({}));
          attendances = Array.isArray(attData)
            ? attData
            : attData.attendances || attData.data || [];
        }

        const rows = [];
        // Mapear cada attendance a una fila en la tabla (ya no incluimos preregistros)
        attendances.forEach((a) => {
          // Resolver nombres que pueden venir a nivel superior o anidados
          const studentName =
            a.student_name ||
            (a.student && (a.student.full_name || a.student.name)) ||
            a.student_full_name ||
            "";
          const studentIdentifier =
            a.student_identifier ||
            (a.student && (a.student.control_number || a.student.control)) ||
            "";
          const activityName =
            a.activity_name ||
            (a.activity && a.activity.name) ||
            a.activity ||
            "";
          const eventName =
            a.event_name ||
            (a.activity && a.activity.event && a.activity.event.name) ||
            "";

          const rawPct = Number(a.attendance_percentage || 0);
          const rawStatus = (a.status || "").toString();
          const isPresent =
            /asist/i.test(rawStatus) ||
            rawPct >= 100 ||
            a.mark_present === true;
          const isError = /err/i.test(rawStatus) || /error/i.test(rawStatus);

          let statusCode = "absent";
          let statusLabel = rawStatus || (isPresent ? "Asistió" : "Faltó");
          if (isPresent) statusCode = "present";
          else if (a.registration_id) statusCode = "registered";
          if (isError) statusCode = "error";

          // formatear fecha de registro usando dateHelpers si está disponible
          var formattedDate = a.created_at || a.date || a.check_in_time || "";
          try {
            if (
              typeof window !== "undefined" &&
              window.dateHelpers &&
              typeof window.dateHelpers.formatDateTime === "function"
            ) {
              formattedDate = window.dateHelpers.formatDateTime(formattedDate);
            }
          } catch (e) {
            // ignore
          }

          rows.push({
            key: `att-${a.id}`,
            registration_id: a.registration_id || null,
            attendance_id: a.id,
            student_id: a.student_id || (a.student && a.student.id) || null,
            student_name: studentName,
            student_identifier: studentIdentifier,
            activity_id: a.activity_id || (a.activity && a.activity.id) || null,
            activity_name: activityName,
            event_name: eventName,
            date: a.created_at || a.date || a.check_in_time || null,
            date_display: formattedDate,
            status: statusCode,
            statusLabel: statusLabel,
            statusClass:
              statusCode === "present"
                ? "text-green-600"
                : statusCode === "registered"
                ? "text-yellow-600"
                : statusCode === "error"
                ? "text-red-600"
                : "text-gray-600",
          });
        });

        this.attendancesTable = rows;

        // Calcular estadísticas simples a partir de rows
        try {
          this.statsToday = (rows || []).length;
          this.statsWalkins = (rows || []).filter(
            (r) => !r.registration_id
          ).length;
          this.statsConverted = (rows || []).filter(
            (r) => r.registration_id && r.attendance_id
          ).length;
          // statsErrors: placeholder - contar filas con status 'Error' o similar
          this.statsErrors = (rows || []).filter((r) => {
            const s = (r.status || "").toString().toLowerCase();
            return s.includes("error") || s.includes("err");
          }).length;
        } catch (e) {
          // ignore
          this.statsToday = 0;
          this.statsWalkins = 0;
          this.statsConverted = 0;
          this.statsErrors = 0;
        }
      } catch (err) {
        console.error(err);
        if (typeof showToast === "function")
          showToast("Error al cargar tabla de asistencias", "error");
        this.attendancesTable = [];
      } finally {
        this.loading = false;
      }
    },

    get attendancesTableFiltered() {
      const q = (this.filters.search || "").toLowerCase().trim();
      return (this.attendancesTable || []).filter((row) => {
        if (
          this.filters.activity_id &&
          String(this.filters.activity_id) !== String(row.activity_id)
        )
          return false;
        if (this.filters.only_without_registration && row.registration_id)
          return false;
        if (!q) return true;
        return (
          (row.student_name || "").toLowerCase().includes(q) ||
          (row.activity_name || "").toLowerCase().includes(q) ||
          (row.event_name || "").toLowerCase().includes(q)
        );
      });
    },

    openEditor(row) {
      try {
        window.dispatchEvent(
          new CustomEvent("open-attendance-editor", { detail: row })
        );
      } catch (e) {
        window.dispatchEvent(new Event("open-attendance-editor"));
      }
    },

    async quickTogglePresent(row) {
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        if (!row.attendance_id) {
          const res = await f("/api/attendances/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              student_id: row.student_id,
              activity_id: row.activity_id,
              mark_present: true,
            }),
          });
          const body = await res.json().catch(() => ({}));
          if (res.ok) {
            if (typeof showToast === "function")
              showToast(body.message || "Asistencia registrada", "success");
            await this.refresh();
            try {
              window.dispatchEvent(
                new CustomEvent("attendance:changed", {
                  detail: {
                    activity_id: row.activity_id,
                    student_id: row.student_id,
                  },
                })
              );
            } catch (e) {
              window.dispatchEvent(new Event("attendance:changed"));
            }
          } else {
            if (typeof showToast === "function")
              showToast(body.message || "Error al registrar", "error");
          }
        } else {
          const res = await f(`/api/attendances/${row.attendance_id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              mark_present: !(
                row.status && row.status.toLowerCase().includes("asist")
              ),
            }),
          });
          const body = await res.json().catch(() => ({}));
          if (res.ok) {
            if (typeof showToast === "function")
              showToast(body.message || "Asistencia actualizada", "success");
            await this.refresh();
            try {
              window.dispatchEvent(
                new CustomEvent("attendance:changed", {
                  detail: {
                    activity_id: row.activity_id,
                    student_id: row.student_id,
                  },
                })
              );
            } catch (e) {
              window.dispatchEvent(new Event("attendance:changed"));
            }
          } else {
            if (typeof showToast === "function")
              showToast(body.message || "Error al actualizar", "error");
          }
        }
      } catch (err) {
        console.error(err);
        if (typeof showToast === "function")
          showToast("Error en acción rápida", "error");
      }
    },

    goToRegistration(row) {
      if (!row.registration_id) return;
      window.location.href = `/admin/registrations/${row.registration_id}`;
    },

    async search() {
      const q = this.query.trim();
      if (!q) return (this.students = []);
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f(
          "/api/students?search=" + encodeURIComponent(q) + "&per_page=10"
        );
        if (!res.ok) throw new Error("Error en búsqueda");
        const data = await res.json();
        this.students = Array.isArray(data) ? data : data.students || [];
      } catch (err) {
        console.error(err);
        this.students = [];
        if (typeof showToast === "function")
          showToast("Error al buscar estudiantes", "error");
      }
    },

    async openQuickRegister(studentId) {
      if (!this.activityId) {
        if (typeof showToast === "function")
          showToast("Selecciona una actividad primero", "warning");
        return;
      }
      const s = (this.students || []).find(
        (x) => Number(x.id) === Number(studentId)
      );
      this.modalStudentId = String(studentId);
      this.modalStudentName = s ? s.full_name || s.name || "" : "";
      const a = (this.activities || []).find(
        (x) => Number(x.id) === Number(this.activityId)
      );
      this.modalActivityId = String(this.activityId);
      this.modalActivityName = a ? a.name || "" : "";
      this.modalMarkPresent = true;
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const params = new URLSearchParams({
          student_id: String(studentId),
          activity_id: String(this.activityId),
        });
        const res = await f(`/api/attendances?${params.toString()}`);
        if (res && res.ok) {
          const data = await res.json().catch(() => ({}));
          let items = [];
          if (Array.isArray(data)) items = data;
          else if (data && Array.isArray(data.attendances))
            items = data.attendances;
          else if (data && Array.isArray(data.data)) items = data.data;
          if (items.length > 0) {
            const att = items[0];
            this.modalMode = "edit";
            this.modalExistingStatus = att.status || "";
            this.modalAttendancePercentage = att.attendance_percentage || 0;
            this.modalMarkPresent =
              att.status === "Asistió" ||
              (att.attendance_percentage || 0) >= 100;
          } else {
            this.modalMode = "create";
            this.modalExistingStatus = "";
            this.modalAttendancePercentage = 0;
            this.modalMarkPresent = true;
          }
        } else {
          this.modalMode = "create";
          this.modalExistingStatus = "";
          this.modalAttendancePercentage = 0;
        }
      } catch (err) {
        console.error(err);
        this.modalMode = "create";
        this.modalExistingStatus = "";
        this.modalAttendancePercentage = 0;
      }
      this.showModal = true;
    },

    openRegister() {
      if (!this.activityId) {
        if (typeof showToast === "function")
          showToast("Selecciona una actividad primero", "warning");
        return;
      }
      const a = (this.activities || []).find(
        (x) => Number(x.id) === Number(this.activityId)
      );
      this.modalActivityId = String(this.activityId);
      this.modalActivityName = a ? a.name || "" : "";
      this.modalStudentId = "";
      this.modalStudentName = "";
      this.modalMarkPresent = true;
      this.showModal = true;
    },

    async submitModal() {
      const sid = Number(this.modalStudentId);
      const aid = Number(this.modalActivityId);
      const markPresent = !!this.modalMarkPresent;
      if (!aid) {
        if (typeof showToast === "function")
          showToast("Actividad no seleccionada", "warning");
        return;
      }
      if (!sid) {
        if (typeof showToast === "function")
          showToast(
            "Selecciona un estudiante o usa la opción Asignar manual",
            "warning"
          );
        return;
      }
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f("/api/attendances/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            student_id: sid,
            activity_id: aid,
            mark_present: markPresent,
          }),
        });
        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          if (typeof showToast === "function")
            showToast(body.message || "Asistencia registrada", "success");
          this.showModal = false;
          this.students = [];
          try {
            window.dispatchEvent(
              new CustomEvent("attendance:changed", {
                detail: { activity_id: aid, student_id: sid },
              })
            );
          } catch (e) {
            try {
              window.dispatchEvent(new Event("attendance:changed"));
            } catch (_) {}
          }
        } else {
          if (typeof showToast === "function")
            showToast(body.message || "Error al registrar", "error");
        }
      } catch (err) {
        console.error(err);
        if (typeof showToast === "function")
          showToast("Error al registrar asistencia", "error");
      }
    },

    async deleteAttendance(row) {
      // row may contain attendance_id or attendance_id may be null
      const aid = row && (row.attendance_id || row.id);
      if (!aid) {
        if (typeof showToast === "function")
          showToast("No se encontró la asistencia a eliminar", "error");
        return;
      }

      // Confirmación simple (no crear ventanas modales nuevas)
      try {
        const proceed =
          typeof window.confirm === "function"
            ? window.confirm(
                "¿Eliminar asistencia? Esta acción no se puede revertir."
              )
            : true;
        if (!proceed) return;

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f(`/api/attendances/${aid}`, { method: "DELETE" });
        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          if (typeof showToast === "function")
            showToast(body.message || "Asistencia eliminada", "success");
          // refrescar tabla
          await this.refresh();
          try {
            window.dispatchEvent(
              new CustomEvent("attendance:changed", {
                detail: { attendance_id: aid },
              })
            );
          } catch (e) {
            try {
              window.dispatchEvent(new Event("attendance:changed"));
            } catch (_) {}
          }
        } else {
          if (typeof showToast === "function")
            showToast(body.message || "Error al eliminar asistencia", "error");
        }
      } catch (err) {
        console.error(err);
        if (typeof showToast === "function")
          showToast("Error al eliminar asistencia", "error");
      }
    },

    closeModal() {
      this.showModal = false;
      this.modalStudentId = "";
      this.modalActivityId = "";
      this.modalMarkPresent = true;
      this.modalStudentName = "";
      this.modalActivityName = "";
    },
  };
}

try {
  document.addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest(".quick-register") : null;
    if (!btn) return;
    var sid = btn.dataset.studentId;
    var alpineRoot = document.querySelector("[x-data]");
    if (
      alpineRoot &&
      alpineRoot.__x &&
      alpineRoot.__x.$data &&
      typeof alpineRoot.__x.$data.openQuickRegister === "function"
    ) {
      alpineRoot.__x.$data.openQuickRegister(Number(sid));
    }
  });
} catch (e) {
  // In non-DOM environments (tests) avoid throwing on import
}

if (typeof window !== "undefined") {
  window.attendancesAdmin = attendancesAdmin;
}
// --- Consolidated additional attendance factories (from other files) ---

// attendancesAssign (consolidated)
function attendancesAssign() {
  return {
    events: [],
    activities: [],
    studentQuery: "",
    studentResults: [],
    selectedEvent: "",
    selectedActivity: "",
    selectedStudent: null,
    // backwards-compatible message for tests / UI
    message: "",
    existingAttendance: {
      id: null,
      status: null,
      attendance_percentage: 0,
      check_in_time: null,
      check_out_time: null,
      check_in_time_input: null,
      check_out_time_input: null,
      mark_present: false,
    },
    assignMode: "create",
    init() {
      this.loadEvents();
    },
    async loadEvents() {
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const res = await f("/api/events?status=active&per_page=1000");
      if (res && res.ok) {
        const data = await res.json().catch(() => []);
        let items = [];
        if (Array.isArray(data)) items = data;
        else if (data && Array.isArray(data.events)) items = data.events;
        else if (data && Array.isArray(data.data)) items = data.data;
        else if (data && Array.isArray(data.items)) items = data.items;
        this.events = items || [];
      }
    },
    async loadActivities() {
      this.selectedActivity = "";
      this.activities = [];
      if (!this.selectedEvent) return;
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const res = await f(`/api/activities?event_id=${this.selectedEvent}`);
      if (res && res.ok) {
        const data = await res.json().catch(() => []);
        let items = [];
        if (Array.isArray(data)) items = data;
        else if (data && Array.isArray(data.activities))
          items = data.activities;
        else if (data && Array.isArray(data.data)) items = data.data;
        else if (data && Array.isArray(data.items)) items = data.items;
        this.activities = items || [];
      }
    },
    async searchStudents() {
      if (this.studentQuery.length < 2) return (this.studentResults = []);
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const res = await f(
        `/api/students/search?q=${encodeURIComponent(this.studentQuery)}`
      );
      if (res.ok) this.studentResults = await res.json();
    },
    selectStudent(student) {
      this.selectedStudent = student;
      this.studentResults = [];
      this.studentQuery = student.full_name;
      // Pre-check for existing attendance when a student is selected
      this.loadExistingAttendance();
    },
    async loadExistingAttendance() {
      this.assignMode = "create";
      this.existingAttendance = {
        id: null,
        status: null,
        attendance_percentage: 0,
        check_in_time: null,
        check_out_time: null,
        check_in_time_input: null,
        check_out_time_input: null,
        mark_present: false,
      };
      if (!this.selectedStudent || !this.selectedActivity) return;
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const params = new URLSearchParams({
          student_id: String(this.selectedStudent.id),
          activity_id: String(this.selectedActivity),
        });
        const res = await f(`/api/attendances?${params.toString()}`);
        if (res && res.ok) {
          const data = await res.json().catch(() => ({}));
          let items = [];
          if (Array.isArray(data)) items = data;
          else if (data && Array.isArray(data.attendances))
            items = data.attendances;
          else if (data && Array.isArray(data.data)) items = data.data;
          if (items.length > 0) {
            const att = items[0];
            this.assignMode = "edit";
            this.existingAttendance.id = att.id;
            this.existingAttendance.status = att.status;
            this.existingAttendance.attendance_percentage =
              att.attendance_percentage || 0;
            this.existingAttendance.check_in_time = att.check_in_time || null;
            this.existingAttendance.check_out_time = att.check_out_time || null;
            function toInput(dt) {
              if (!dt) return null;
              try {
                const d = new Date(dt);
                if (isNaN(d.getTime())) return null;
                const pad = (n) => String(n).padStart(2, "0");
                return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(
                  d.getDate()
                )}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
              } catch (e) {
                return null;
              }
            }
            this.existingAttendance.check_in_time_input = toInput(
              this.existingAttendance.check_in_time
            );
            this.existingAttendance.check_out_time_input = toInput(
              this.existingAttendance.check_out_time
            );
            this.existingAttendance.mark_present =
              this.existingAttendance.status === "Asisti3" ||
              (this.existingAttendance.attendance_percentage || 0) >= 100;
          } else {
            this.assignMode = "create";
          }
        }
      } catch (err) {
        console.error(err);
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

          try {
            window.dispatchEvent(
              new CustomEvent("attendance:changed", {
                detail: {
                  activity_id: this.selectedActivity,
                  student_id: dispatchedStudentId,
                },
              })
            );
          } catch (e) {
            try {
              window.dispatchEvent(new Event("attendance:changed"));
            } catch (_) {}
          }
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
  };
}

// attendancesList (consolidated)
function attendancesList() {
  return {
    events: [],
    activities: [],
    attendances: [],
    selectedEvent: "",
    selectedActivity: "",
    studentQuery: "",
    studentResults: [],
    selectedStudent: null,
    init() {
      this.loadEvents();
      this.loadAttendances();
    },
    async loadEvents() {
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const res = await f("/api/events");
      if (res.ok) this.events = await res.json();
    },
    async loadActivities() {
      this.selectedActivity = "";
      this.activities = [];
      if (!this.selectedEvent) return this.loadAttendances();
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const res = await f(`/api/activities?event_id=${this.selectedEvent}`);
      if (res.ok) this.activities = await res.json();
      this.loadAttendances();
    },
    async searchStudents() {
      if (this.studentQuery.length < 2) return (this.studentResults = []);
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const res = await f(
        `/api/students/search?q=${encodeURIComponent(this.studentQuery)}`
      );
      if (res.ok) this.studentResults = await res.json();
    },
    selectStudent(student) {
      this.selectedStudent = student;
      this.studentResults = [];
      this.studentQuery = student.full_name;
      this.loadAttendances();
    },
    clearFilters() {
      this.selectedEvent = "";
      this.selectedActivity = "";
      this.selectedStudent = null;
      this.studentQuery = "";
      this.loadAttendances();
    },
    async loadAttendances() {
      const params = new URLSearchParams();
      if (this.selectedEvent) params.append("event_id", this.selectedEvent);
      if (this.selectedActivity)
        params.append("activity_id", this.selectedActivity);
      if (this.selectedStudent)
        params.append("student_id", this.selectedStudent.id);

      const url = `/api/attendances?${params.toString()}`;
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const res = await f(url);
      if (!res.ok) return (this.attendances = []);

      try {
        const data = await res.json();
        let items = [];
        if (Array.isArray(data)) items = data;
        else if (data && Array.isArray(data.attendances))
          items = data.attendances;
        else if (data && Array.isArray(data.data)) items = data.data;

        this.attendances = items.map((att) => ({
          id: att.id,
          student_name: att.student_name || att.student?.full_name || "",
          activity_name: att.activity_name || att.activity?.name || "",
          event_name: att.event_name || att.activity?.event?.name || "",
          date: (function () {
            try {
              const helpers = require("../helpers/dateHelpers");
              const input = helpers.formatDateTimeForInput(att.check_in);
              return input
                ? input.slice(0, 10)
                : att.check_in
                ? att.check_in.split("T")[0]
                : "";
            } catch (e) {
              return att.check_in ? att.check_in.split("T")[0] : "";
            }
          })(),
          status: att.status,
        }));
      } catch (e) {
        this.attendances = [];
      }
    },
  };
}

// attendancesRoster (consolidated)
function attendancesRoster() {
  return {
    events: [],
    activities: [],
    registrations: [],
    selectedEvent: "",
    selectedActivity: "",
    selectedIds: new Set(),
    loading: false,

    init() {
      this.loadEvents();
    },

    async loadEvents() {
      const sf = window.safeFetch || fetch;
      try {
        const res = await sf("/api/events?status=active&per_page=1000");
        if (!res.ok) throw new Error("No se pudieron cargar eventos");
        const data = await res.json().catch(() => ({}));
        this.events = data.events || [];
      } catch (err) {
        console.error(err);
        showToast("Error al cargar eventos", "error");
      }
    },

    async loadActivities() {
      if (!this.selectedEvent) {
        this.activities = [];
        return;
      }
      const sf = window.safeFetch || fetch;
      try {
        const res = await sf(
          `/api/activities?event_id=${this.selectedEvent}&per_page=1000`
        );
        if (!res.ok) throw new Error("No se pudieron cargar actividades");
        const data = await res.json().catch(() => ({}));
        this.activities = data.activities || [];
      } catch (err) {
        console.error(err);
        showToast("Error al cargar actividades", "error");
      }
    },

    async loadRegistrations() {
      if (!this.selectedActivity) {
        this.registrations = [];
        return;
      }
      const sf = window.safeFetch || fetch;
      this.loading = true;
      try {
        const res = await sf(
          `/api/registrations?activity_id=${this.selectedActivity}&per_page=1000`
        );
        if (!res.ok) throw new Error("Error al cargar preregistros");
        const data = await res.json().catch(() => ({}));
        this.registrations = data.registrations || [];
        this.selectedIds = new Set();
      } catch (err) {
        console.error(err);
        showToast("Error al cargar preregistros", "error");
      } finally {
        this.loading = false;
      }
    },

    toggleSelection(reg) {
      if (this.selectedIds.has(reg.id)) {
        this.selectedIds.delete(reg.id);
      } else {
        this.selectedIds.add(reg.id);
      }
    },

    isSelected(reg) {
      return this.selectedIds.has(reg.id);
    },

    toggleSelectAll(e) {
      if (e.target.checked) {
        this.registrations.forEach((r) => this.selectedIds.add(r.id));
      } else {
        this.selectedIds = new Set();
      }
    },

    async markSelected() {
      if (!this.selectedActivity) {
        showToast("Selecciona una actividad primero", "warning");
        return;
      }
      if (this.selectedIds.size === 0) {
        showToast("Selecciona al menos un preregistro", "warning");
        return;
      }

      const studentIds = [];
      this.registrations.forEach((r) => {
        if (this.selectedIds.has(r.id)) {
          if (r.student && r.student.id) studentIds.push(r.student.id);
        }
      });

      if (studentIds.length === 0) {
        showToast(
          "No se encontr\u00f3 estudiante para los preregistros seleccionados",
          "error"
        );
        return;
      }

      try {
        const sf = window.safeFetch || fetch;
        const res = await sf("/api/attendances/bulk-create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            activity_id: Number(this.selectedActivity),
            student_ids: studentIds,
          }),
        });
        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          showToast(body.message || "Asistencias creadas", "success");
          await this.loadRegistrations();
          try {
            window.dispatchEvent(
              new CustomEvent("attendance:changed", {
                detail: { activity_id: Number(this.selectedActivity) },
              })
            );
          } catch (e) {
            try {
              window.dispatchEvent(new Event("attendance:changed"));
            } catch (_) {}
          }
        } else {
          showToast(body.message || "Error al marcar asistentes", "error");
        }
      } catch (err) {
        console.error(err);
        showToast("Error al marcar asistentes", "error");
      }
    },

    printRoster() {
      const rows = this.registrations
        .map((r) => {
          const name =
            (r.student && (r.student.full_name || r.student.name)) ||
            "Desconocido";
          const control = (r.student && r.student.control_number) || "";
          const activity = (r.activity && r.activity.name) || "";
          return `<tr><td style="padding:4px;border:1px solid #ddd">${name}</td><td style="padding:4px;border:1px solid #ddd">${control}</td><td style="padding:4px;border:1px solid #ddd">${activity}</td><td style="padding:4px;border:1px solid #ddd">_____</td></tr>`;
        })
        .join("");

      const activityName =
        this.activities.find((a) => a.id == this.selectedActivity)?.name || "";
      const html = `<!doctype html><html><head><meta charset="utf-8"><title>Roster</title><style>table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:8px}</style></head><body><h3>Roster - ${activityName}</h3><table><thead><tr><th>Estudiante</th><th>Control</th><th>Actividad</th><th>Firma</th></tr></thead><tbody>${rows}</tbody></table></body></html>`;
      const w = window.open("", "_blank");
      w.document.write(html);
      w.document.close();
      w.print();
    },
  };
}

// attendancesStudent (consolidated)
function attendancesStudent() {
  return {
    query: "",
    student: null,
    registrations: [],
    loading: false,

    init() {},

    async searchStudent() {
      const q = this.query.trim();
      if (!q) return;
      this.loading = true;
      try {
        const sf = window.safeFetch || fetch;
        const res = await sf(
          `/api/students?search=${encodeURIComponent(q)}&per_page=1`
        );
        if (!res.ok) throw new Error("Error al buscar estudiante");
        const data = await res.json().catch(() => ({}));
        const students = data.students || [];
        if (students.length === 0) {
          showToast("No se encontr\u00f3 el estudiante", "warning");
          this.student = null;
          this.registrations = [];
        } else {
          this.student = students[0];
          await this.loadRegistrationsForStudent(this.student.id);
        }
      } catch (err) {
        console.error(err);
        showToast("Error al buscar estudiante", "error");
      } finally {
        this.loading = false;
      }
    },

    async loadRegistrationsForStudent(studentId) {
      const sf = window.safeFetch || fetch;
      try {
        const res = await sf(
          `/api/registrations?student_id=${studentId}&per_page=1000`
        );
        if (!res.ok) throw new Error("Error al cargar preregistros");
        const data = await res.json().catch(() => ({}));
        this.registrations = data.registrations || [];
      } catch (err) {
        console.error(err);
        showToast("Error al cargar preregistros", "error");
      }
    },

    async updateRegistration(reg) {
      try {
        const sf = window.safeFetch || fetch;
        const res = await sf(`/api/registrations/${reg.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            status: reg.status,
            attended: reg.status === "Asisti\u00f3",
          }),
        });
        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          showToast("Registro actualizado", "success");
          if (this.student)
            await this.loadRegistrationsForStudent(this.student.id);
        } else {
          showToast(body.message || "Error al actualizar registro", "error");
        }
      } catch (err) {
        console.error(err);
        showToast("Error al actualizar registro", "error");
      }
    },

    async markAttendance(reg) {
      try {
        const payload = {
          student_id: reg.student_id || reg.student?.id,
          activity_id: reg.activity_id || reg.activity?.id,
          mark_present: true,
        };
        const sf = window.safeFetch || fetch;
        const res = await sf("/api/attendances/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          showToast("Asistencia marcada", "success");
          if (this.student)
            await this.loadRegistrationsForStudent(this.student.id);
        } else {
          showToast(body.message || "Error al marcar asistencia", "error");
        }
      } catch (err) {
        console.error(err);
        showToast("Error al marcar asistencia", "error");
      }
    },
  };
}

// expose consolidated factories to window
try {
  window.attendancesAssign = attendancesAssign;
  window.attendancesList = attendancesList;
  window.attendancesRoster = attendancesRoster;
  window.attendancesStudent = attendancesStudent;
} catch (e) {}

// Export factories for tests (module.exports as object to preserve compatibility)
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    attendancesAdmin,
    attendancesAssign,
    attendancesList,
    attendancesRoster,
    attendancesStudent,
  };
}

// Also provide a `default` field for environments that `require()` the file
// and then try to access `.default` (ES module interop in some bundlers/tests).
try {
  if (typeof module !== "undefined" && module.exports)
    module.exports.default = module.exports;
} catch (e) {}
