// static/js/student/history.js
function studentHistoryManager() {
  return {
    // Estado
    eventsHours: [],
    loading: false,
    errorMessage: "",
    studentId: null,

    // Modal de detalle de evento
    showEventDetailModal: false,
    currentEventDetail: null,
    eventActivities: [],
    loadingEventDetail: false,

    // Inicialización
    async init() {
      this.studentId = this.getCurrentStudentId();
      if (this.studentId) {
        await this.loadHistory();
      } else {
        this.errorMessage = "No se pudo obtener información del estudiante";
      }
    },

    // Cargar histórico de horas por evento
    async loadHistory() {
      this.loading = true;
      this.errorMessage = "";

      try {
        const response = await fetch(
          `/api/students/${this.studentId}/hours-by-event`,
          {
            headers: window.getAuthHeaders(),
          }
        );

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(`Error: ${response.status}`);
        }

        const data = await response.json();
        this.eventsHours = data.events_hours || [];
      } catch (error) {
        console.error("Error loading history:", error);
        this.errorMessage = "Error al cargar el histórico";
        window.showToast && window.showToast(this.errorMessage, "error");
      } finally {
        this.loading = false;
      }
    },

    // Ver detalle de actividades de un evento
    async viewEventDetail(eventData) {
      this.currentEventDetail = { ...eventData };
      this.eventActivities = [];
      this.showEventDetailModal = true;
      this.loadingEventDetail = true;

      try {
        const response = await fetch(
          `/api/students/${this.studentId}/event/${eventData.event_id}/details`,
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

    // Cerrar modal de detalle
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

    // Obtener ID del estudiante actual
    getCurrentStudentId() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) return null;

        // Decodificar el token JWT para obtener el ID del usuario
        const payload = JSON.parse(atob(token.split(".")[1]));
        return payload.sub; // El ID del usuario está en el claim 'sub'
      } catch (e) {
        console.error("Error decoding token:", e);
        return null;
      }
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
  window.studentHistoryManager = studentHistoryManager;
}

// Para compatibilidad con Node (tests)
if (typeof module !== "undefined" && module.exports) {
  module.exports = studentHistoryManager;
}
