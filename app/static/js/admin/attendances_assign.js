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
      const res = await fetch("/api/events");
      if (res.ok) {
        this.events = await res.json();
      }
    },
    async loadActivities() {
      this.selectedActivity = "";
      this.activities = [];
      if (!this.selectedEvent) return;
      const res = await fetch(`/api/activities?event_id=${this.selectedEvent}`);
      if (res.ok) {
        this.activities = await res.json();
      }
    },
    async searchStudents() {
      if (this.studentQuery.length < 2) {
        this.studentResults = [];
        return;
      }
      const res = await fetch(
        `/api/students/search?q=${encodeURIComponent(this.studentQuery)}`
      );
      if (res.ok) {
        this.studentResults = await res.json();
      }
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
      const res = await fetch("/api/attendances/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
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
    },
  };
}
window.attendancesAssign = attendancesAssign;
