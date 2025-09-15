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
        `/api/students/search?q=${encodeURIComponent(this.studentQuery)}`,
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
          date: att.check_in ? att.check_in.split("T")[0] : "",
          status: att.status,
        }));
      } catch (e) {
        this.attendances = [];
      }
    },
  };
}
// Make the factory available to Alpine in the browser
try {
  window.attendancesList = attendancesList;
} catch (e) {
  // non-browser (tests)
}

// Export for Node/Jest
if (typeof module !== "undefined" && module.exports) {
  module.exports = attendancesList;
}
