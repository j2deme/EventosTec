function attendancesAssign() {
  return {
    events: [],
    activities: [],
    studentQuery: "",
    studentResults: [],
    selectedEvent: "",
    selectedActivity: "",
    selectedStudent: null,
    message: "",
    error: "",
    init() {
      this.loadEvents();
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
      if (!this.selectedEvent) return;
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const res = await f(`/api/activities?event_id=${this.selectedEvent}`);
      if (res.ok) this.activities = await res.json();
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
    },
    async submitAssign() {
      this.message = "";
      this.error = "";
      if (!this.selectedActivity || !this.selectedStudent) return;
      const payload = {
        activity_id: this.selectedActivity,
        student_id: this.selectedStudent.id,
        mark_present: true,
      };
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f("/api/attendances/register", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          this.message = "Asistencia asignada correctamente.";
          this.selectedStudent = null;
          this.studentQuery = "";
        } else {
          const data = await res.json().catch(() => ({}));
          this.error = data.message || "Error al asignar asistencia.";
        }
      } catch (err) {
        this.error = "Error de conexión al asignar asistencia.";
      }
    },
  };
}
// Make the factory available to Alpine in the browser
try {
  window.attendancesAssign = attendancesAssign;
} catch (e) {
  // running in non-browser environment (tests)
}

// Export for Node/Jest
if (typeof module !== "undefined" && module.exports) {
  module.exports = attendancesAssign;
}
