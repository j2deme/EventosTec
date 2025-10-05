// static/js/admin/students.js
function studentsAdmin() {
  return {
    // Estado
    students: [],
    loading: false,
    errorMessage: "",

    // Paginación
    pagination: {
      current_page: 1,
      last_page: 1,
      total: 0,
      from: 0,
      to: 0,
      pages: [],
    },

    // Filtros
    filters: {
      search: "",
      event_id: null,
      activity_id: null,
      career: "",
    },

    // Para los selectores de filtros
    events: [],
    activities: [],
    allActivities: [],
    careers: [],

    // Modal de detalle del estudiante
    showDetailModal: false,
    currentStudent: null,
    studentEventsHours: [],
    loadingDetail: false,

    // Modal de detalle de evento específico
    showEventDetailModal: false,
    currentEventDetail: null,
    eventActivities: [],
    loadingEventDetail: false,

    // Inicialización
    async init() {
      await this.loadEvents();
      await this.loadAllActivities();
      await this.loadStudents(1);
    },

    // Cargar estudiantes con filtros
    async loadStudents(page = 1) {
      this.loading = true;
      this.errorMessage = "";

      try {
        const params = new URLSearchParams({
          page: page,
          per_page: 10,
        });

        if (this.filters.search) {
          params.append("search", this.filters.search);
        }
        if (this.filters.event_id) {
          params.append("event_id", this.filters.event_id);
        }
        if (this.filters.activity_id) {
          params.append("activity_id", this.filters.activity_id);
        }
        if (this.filters.career) {
          params.append("career", this.filters.career);
        }

        const response = await fetch(`/api/students?${params}`, {
          headers: window.getAuthHeaders(),
        });

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(`Error: ${response.status}`);
        }

        const data = await response.json();
        this.students = data.students || [];
        
        this.pagination = {
          current_page: data.current_page || 1,
          last_page: data.pages || 1,
          total: data.total || 0,
          from: this.students.length > 0 ? (data.current_page - 1) * 10 + 1 : 0,
          to: Math.min(data.current_page * 10, data.total || 0),
          pages: Array.from({ length: data.pages || 1 }, (_, i) => i + 1),
        };

      } catch (error) {
        console.error("Error loading students:", error);
        this.errorMessage = "Error al cargar estudiantes";
        window.showToast && window.showToast(this.errorMessage, "error");
      } finally {
        this.loading = false;
      }
    },

    // Cargar eventos para el filtro
    async loadEvents() {
      try {
        const response = await fetch("/api/events", {
          headers: window.getAuthHeaders(),
        });

        if (response.ok) {
          const data = await response.json();
          this.events = data.events || [];
        }
      } catch (error) {
        console.error("Error loading events:", error);
      }
    },

    // Cargar todas las actividades
    async loadAllActivities() {
      try {
        const response = await fetch("/api/activities?per_page=1000", {
          headers: window.getAuthHeaders(),
        });

        if (response.ok) {
          const data = await response.json();
          this.allActivities = data.activities || [];
          this.updateActivitiesFilter();
        }
      } catch (error) {
        console.error("Error loading activities:", error);
      }
    },

    // Actualizar actividades según evento seleccionado
    updateActivitiesFilter() {
      if (this.filters.event_id) {
        this.activities = this.allActivities.filter(
          (a) => a.event_id === parseInt(this.filters.event_id)
        );
      } else {
        this.activities = this.allActivities;
      }
      
      // Reset activity filter if not in filtered list
      if (this.filters.activity_id) {
        const exists = this.activities.find(
          (a) => a.id === parseInt(this.filters.activity_id)
        );
        if (!exists) {
          this.filters.activity_id = null;
        }
      }
    },

    // Aplicar filtros
    applyFilters() {
      this.updateActivitiesFilter();
      this.loadStudents(1);
    },

    // Limpiar filtros
    clearFilters() {
      this.filters = {
        search: "",
        event_id: null,
        activity_id: null,
        career: "",
      };
      this.activities = this.allActivities;
      this.loadStudents(1);
    },

    // Cambiar página
    changePage(page) {
      if (page >= 1 && page <= this.pagination.last_page) {
        this.loadStudents(page);
      }
    },

    // Ver detalle de estudiante
    async viewStudentDetail(student) {
      this.currentStudent = { ...student };
      this.studentEventsHours = [];
      this.showDetailModal = true;
      this.loadingDetail = true;

      try {
        const response = await fetch(
          `/api/students/${student.id}/hours-by-event`,
          {
            headers: window.getAuthHeaders(),
          }
        );

        if (!response.ok) {
          throw new Error(`Error: ${response.status}`);
        }

        const data = await response.json();
        this.studentEventsHours = data.events_hours || [];
      } catch (error) {
        console.error("Error loading student details:", error);
        window.showToast && window.showToast("Error al cargar detalles", "error");
      } finally {
        this.loadingDetail = false;
      }
    },

    // Cerrar modal de detalle
    closeDetailModal() {
      this.showDetailModal = false;
      this.currentStudent = null;
      this.studentEventsHours = [];
    },

    // Ver detalle de evento específico
    async viewEventDetail(eventData) {
      if (!this.currentStudent) return;

      this.currentEventDetail = { ...eventData };
      this.eventActivities = [];
      this.showEventDetailModal = true;
      this.loadingEventDetail = true;

      try {
        const response = await fetch(
          `/api/students/${this.currentStudent.id}/event/${eventData.event_id}/details`,
          {
            headers: window.getAuthHeaders(),
          }
        );

        if (!response.ok) {
          throw new Error(`Error: ${response.status}`);
        }

        const data = await response.json();
        this.eventActivities = data.activities || [];
        this.currentEventDetail.total_confirmed_hours = data.total_confirmed_hours;
        this.currentEventDetail.has_complementary_credit = data.has_complementary_credit;
      } catch (error) {
        console.error("Error loading event details:", error);
        window.showToast && window.showToast("Error al cargar actividades", "error");
      } finally {
        this.loadingEventDetail = false;
      }
    },

    // Cerrar modal de detalle de evento
    closeEventDetailModal() {
      this.showEventDetailModal = false;
      this.currentEventDetail = null;
      this.eventActivities = [];
    },

    // Formatear fecha
    formatDate(dateString) {
      if (!dateString) return "Sin fecha";
      const date = new Date(dateString);
      return date.toLocaleDateString("es-ES", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    },

    // Formatear fecha y hora
    formatDateTime(dateString) {
      if (!dateString) return "Sin fecha";
      const date = new Date(dateString);
      return date.toLocaleString("es-ES", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    },

    // Obtener clase de badge de status
    getStatusBadgeClass(status) {
      const classes = {
        Registrado: "bg-yellow-100 text-yellow-800",
        Confirmado: "bg-blue-100 text-blue-800",
        Asistió: "bg-green-100 text-green-800",
        Ausente: "bg-red-100 text-red-800",
        Cancelado: "bg-gray-100 text-gray-800",
      };
      return classes[status] || "bg-gray-100 text-gray-800";
    },

    // Redireccionar al login
    redirectToLogin() {
      localStorage.removeItem("authToken");
      localStorage.removeItem("userType");
      window.location.href = "/";
    },
  };
}

// Hacer la función globalmente disponible
if (typeof window !== "undefined") {
  window.studentsAdmin = studentsAdmin;
}

// Para compatibilidad con Node (tests)
if (typeof module !== "undefined" && module.exports) {
  module.exports = studentsAdmin;
}
