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

    // Inicialización
    init() {
      console.log("Initializing student events manager...");
      this.loadEvents();
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
          per_page: 20, // Cambiado a 20 eventos por página para compensar el filtrado
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
        // Nota: El ordenamiento debería venir del backend para ser más eficiente
        // pero lo hacemos aquí para simplicidad
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

        // ✨ Implementar paginación manual
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

    // Cambiar página
    changePage(page) {
      if (page >= 1 && page <= this.pagination.last_page) {
        this.loadEvents(page);
      }
    },

    // Ver detalles del evento
    viewEventDetails(event) {
      this.currentEvent = { ...event };
      this.showEventModal = true;
    },

    // Ver actividades del evento
    viewActivities(event) {
      // Cambiar a la pestaña de actividades con el filtro del evento
      const dashboard = document.querySelector('[x-data*="studentDashboard"]');
      if (dashboard && dashboard.__x) {
        dashboard.__x.getUnobservedData().setActiveTab("registrations");
        // Aquí podrías pasar el event_id al componente de actividades
        window.dispatchEvent(
          new CustomEvent("filter-activities-by-event", {
            detail: { eventId: event.id },
          })
        );
      }
    },

    // Formatear fecha para input datetime-local
    formatDateTimeForInput(dateTimeString) {
      if (!dateTimeString) return "";
      // Convertir a formato YYYY-MM-DDTHH:MM
      const date = new Date(dateTimeString);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      const hours = String(date.getHours()).padStart(2, "0");
      const minutes = String(date.getMinutes()).padStart(2, "0");
      return `${year}-${month}-${day}T${hours}:${minutes}`;
    },

    // Formatear fecha para mostrar
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
