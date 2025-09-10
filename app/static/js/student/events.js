// static/js/student/events.js
console.log("Student Events Manager JS loaded");

function studentEventsManager() {
  return {
    // Estado
    events: [],
    allEvents: [],
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
      sort: "created_at:desc",
    },

    // Modal
    showEventModal: false,
    currentEvent: {},
    currentEventActivitiesSummary: {}, // Para almacenar el resumen de tipos

    // Inicialización
    init() {
      console.log("Initializing student events manager...");
      this.loadEvents();
      this.loadStudentRegistrations();
    },

    // Cargar eventos
    async loadEvents(page = 1) {
      this.loading = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        // Construir parámetros de consulta
        const params = new URLSearchParams({
          page: page,
          per_page: 20,
          ...(this.filters.search && { search: this.filters.search }),
          ...(this.filters.sort && { sort: this.filters.sort }),
        });

        const response = await fetch(`/api/events?${params.toString()}`, {
          headers: window.getAuthHeaders(),
        });

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(
            `Error al cargar eventos: ${response.status} ${response.statusText}`
          );
        }

        const data = await response.json();

        // Filtrar eventos: solo activos y que no hayan terminado
        const now = new Date();
        this.allEvents = data.events.filter((event) => {
          const eventEndDate = new Date(event.end_date);
          return event.is_active === true && eventEndDate >= now;
        });

        // Aplicar búsqueda adicional si existe
        let filteredEvents = this.allEvents;
        if (this.filters.search) {
          const searchTerm = this.filters.search.toLowerCase();
          filteredEvents = this.allEvents.filter(
            (event) =>
              event.name.toLowerCase().includes(searchTerm) ||
              (event.description &&
                event.description.toLowerCase().includes(searchTerm))
          );
        }

        // Aplicar ordenamiento
        if (this.filters.sort) {
          const [field, direction] = this.filters.sort.split(":");
          filteredEvents.sort((a, b) => {
            let aValue = a[field];
            let bValue = b[field];

            // Convertir fechas a objetos Date para comparación
            if (field.includes("date")) {
              aValue = new Date(aValue);
              bValue = new Date(bValue);
            }

            if (direction === "asc") {
              return aValue > bValue ? 1 : aValue < bValue ? -1 : 0;
            } else {
              return aValue < bValue ? 1 : aValue > bValue ? -1 : 0;
            }
          });
        }

        // Implementar paginación manual
        const perPage = 6;
        const totalPages = Math.ceil(filteredEvents.length / perPage);
        const currentPageEvents = filteredEvents.slice(
          (page - 1) * perPage,
          page * perPage
        );

        // Mapear eventos y formatear fechas
        this.events = currentPageEvents.map((event) => ({
          ...event,
          start_date: this.formatDateTimeForInput(event.start_date),
          end_date: this.formatDateTimeForInput(event.end_date),
        }));

        // Actualizar paginación
        this.pagination = {
          current_page: page,
          last_page: totalPages || 1,
          total: filteredEvents.length,
          from: filteredEvents.length > 0 ? (page - 1) * perPage + 1 : 0,
          to: Math.min(page * perPage, filteredEvents.length),
          pages: Array.from({ length: totalPages || 1 }, (_, i) => i + 1),
        };
      } catch (error) {
        console.error("Error loading events:", error);
        this.errorMessage = error.message || "Error al cargar eventos";
        showToast(this.errorMessage, "error");
      } finally {
        this.loading = false;
      }
    },

    async loadStudentRegistrations() {
      // Esta función puede permanecer igual o simplificarse
      // Ya que su lógica principal está en event_activities.js
    },

    // Cambiar página
    changePage(page) {
      if (page >= 1 && page <= this.pagination.last_page) {
        this.loadEvents(page);
      }
    },

    // ✨ Ver detalles del evento (SIMPLIFICADO)
    async viewEventDetails(event) {
      this.currentEvent = { ...event };
      this.currentEventActivitiesSummary = {}; // Reiniciar resumen

      // Cargar un resumen de tipos de actividades del evento
      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        // Obtener todas las actividades del evento sin paginación
        const response = await fetch(
          `/api/activities?event_id=${event.id}&per_page=1000`,
          {
            headers: window.getAuthHeaders(),
          }
        );

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(
            `Error al cargar actividades: ${response.status} ${response.statusText}`
          );
        }

        const data = await response.json();
        const activities = data.activities || [];

        // ✨ Generar resumen por tipo de actividad
        const summary = {};
        activities.forEach((activity) => {
          const type = activity.activity_type || "Otro";
          if (!summary[type]) {
            summary[type] = 0;
          }
          summary[type]++;
        });

        this.currentEventActivitiesSummary = summary;
        this.showEventModal = true;
      } catch (error) {
        console.error("Error loading event activities summary:", error);
        showToast("Error al cargar resumen de actividades", "error");
        this.currentEventActivitiesSummary = {};
        this.showEventModal = true; // Mostrar modal aunque falle el resumen
      }
    },

    // Ver actividades del evento (NAVEGACIÓN)
    viewActivities(event) {
      console.log("Viewing activities for event:", event.id);

      try {
        // ✨ Método más robusto para encontrar y cambiar la pestaña
        let dashboard = null;

        // Intentar encontrar el dashboard de varias maneras
        const possibleSelectors = [
          '[x-data*="studentDashboard"]',
          '[x-data^="studentDashboard"]',
          "[x-data]",
        ];

        for (let selector of possibleSelectors) {
          const elements = document.querySelectorAll(selector);
          for (let element of elements) {
            if (
              element.__x &&
              typeof element.__x.getUnobservedData === "function"
            ) {
              const data = element.__x.getUnobservedData();
              if (data && typeof data.setActiveTab === "function") {
                dashboard = element;
                break;
              }
            }
          }
          if (dashboard) break;
        }

        if (dashboard && dashboard.__x) {
          console.log(
            "Dashboard encontrado, cambiando pestaña a event_activities"
          );

          // Primero cambiar la pestaña
          dashboard.__x.getUnobservedData().setActiveTab("event_activities");

          // Luego enviar el evento para que la vista de actividades lo cargue
          // Usamos un pequeño retraso para asegurar que la pestaña haya cambiado
          setTimeout(() => {
            window.dispatchEvent(
              new CustomEvent("load-event-activities", {
                detail: {
                  eventId: event.id,
                  eventName: event.name,
                },
              })
            );
          }, 150); // ✨ Aumentado el retraso a 150ms
        } else {
          // ✨ Si no encontramos el dashboard de la manera tradicional,
          // intentar una navegación directa
          console.log(
            "Dashboard no encontrado por selector, intentando navegación directa"
          );

          // Cambiar el hash directamente
          window.location.hash = "event_activities";

          // También enviar el evento por si acaso
          setTimeout(() => {
            window.dispatchEvent(
              new CustomEvent("load-event-activities", {
                detail: {
                  eventId: event.id,
                  eventName: event.name,
                },
              })
            );
          }, 200);
        }
      } catch (error) {
        console.error("Error al navegar a actividades:", error);
        showToast("Error al navegar a las actividades", "error");

        // ✨ Como último recurso, intentar navegación directa
        try {
          window.location.hash = `event_activities?event_id=${event.id}`;
        } catch (fallbackError) {
          console.error("Error en navegación de fallback:", fallbackError);
          showToast("Error al navegar a las actividades", "error");
        }
      }
    },

    // Formatear fecha para input datetime-local
    formatDateTimeForInput(dateTimeString) {
      if (!dateTimeString) return "";
      const date = new Date(dateTimeString);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      const hours = String(date.getHours()).padStart(2, "0");
      const minutes = String(date.getMinutes()).padStart(2, "0");
      return `${year}-${month}-${day}T${hours}:${minutes}`;
    },

    // Formatear solo fecha para mostrar
    formatDate(dateTimeString) {
      if (!dateTimeString) return "Sin fecha";
      const date = new Date(dateTimeString);
      return date.toLocaleDateString("es-ES", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    },

    // Formatear fecha y hora para mostrar
    formatDateTime(dateTimeString) {
      if (!dateTimeString) return "Sin fecha";
      const date = new Date(dateTimeString);
      return date.toLocaleString("es-ES", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    },

    formatTime(dateTimeString) {
      if (!dateTimeString) return "--:--";
      const date = new Date(dateTimeString);
      return date.toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
      });
    },

    // Redirigir al login
    redirectToLogin() {
      localStorage.removeItem("authToken");
      localStorage.removeItem("userType");
      localStorage.removeItem("studentProfile");
      window.location.href = "/";
    },
  };
}

// Hacer la función globalmente disponible
window.studentEventsManager = studentEventsManager;
