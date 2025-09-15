// app/static/js/admin/attendances_student.js
function attendancesStudent() {
  return {
    query: "",
    student: null,
    registrations: [],
    loading: false,

    init() {
      // noop
    },

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
          showToast("No se encontró el estudiante", "warning");
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
            attended: reg.status === "Asistió",
          }),
        });
        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          showToast("Registro actualizado", "success");
          // recargar lista
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
          // recargar preregistros
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

// Expose to browser
try {
  window.attendancesStudent = attendancesStudent;
} catch (e) {
  // non-browser
}

// Export for Node/Jest
if (typeof module !== "undefined" && module.exports) {
  module.exports = attendancesStudent;
}
