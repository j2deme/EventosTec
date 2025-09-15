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
      const res = await fetch("/api/events");
      if (res.ok) {
        this.events = await res.json();
      }
    },
    async loadActivities() {
      this.selectedActivity = "";
      this.activities = [];
      if (!this.selectedEvent) {
        this.loadAttendances();
        return;
      }
      const res = await fetch(`/api/activities?event_id=${this.selectedEvent}`);
      if (res.ok) {
        this.activities = await res.json();
      }
      this.loadAttendances();
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
      let url = "/api/attendances?";
      if (this.selectedEvent) url += `event_id=${this.selectedEvent}&`;
      if (this.selectedActivity) url += `activity_id=${this.selectedActivity}&`;
      if (this.selectedStudent) url += `student_id=${this.selectedStudent.id}&`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        this.attendances = data.map((att) => ({
          id: att.id,
          student_name: att.student_name || att.student?.full_name || "",
          activity_name: att.activity_name || att.activity?.name || "",
          event_name: att.event_name || att.activity?.event?.name || "",
          date: att.check_in ? att.check_in.split("T")[0] : "",
          status: att.status,
        }));
      }
    },
  };
}
window.attendancesList = attendancesList;
