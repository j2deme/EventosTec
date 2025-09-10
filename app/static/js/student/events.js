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
    currentEventActivities: [],
    studentRegistrations: [],

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
        // Pedimos más eventos para tener margen al filtrar
        const params = new URLSearchParams({
          page: page,
          per_page: 20, // Pedimos más para compensar el filtrado
          ...(this.filters.search && { search: this.filters.search }),
          // Removemos status ya que lo filtraremos en el frontend
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
      try {
        const token = localStorage.getItem("authToken");
        if (!token) return;

        const studentId = this.getCurrentStudentId();
        if (!studentId) return;

        const response = await fetch(
          `/api/registrations?student_id=${studentId}`,
          {
            headers: window.getAuthHeaders(),
          }
        );

        if (response.ok) {
          const data = await response.json();
          // Solo necesitamos los IDs de las actividades registradas
          this.studentRegistrations = data.registrations.map(
            (r) => r.activity_id
          );
          console.log("Preregistros cargados:", this.studentRegistrations);
        }
      } catch (error) {
        console.error("Error loading student registrations:", error);
        // No es crítico, solo para la UI
      }
    },

    // Cambiar página
    changePage(page) {
      if (page >= 1 && page <= this.pagination.last_page) {
        this.loadEvents(page);
      }
    },

    // Ver detalles del evento
    async viewEventDetails(event) {
      this.currentEvent = { ...event };

      // Cargar actividades del evento
      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        const response = await fetch(`/api/activities?event_id=${event.id}`, {
          headers: window.getAuthHeaders(),
        });

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

        // Mapear actividades y formatear fechas
        this.currentEventActivities = data.activities.map((activity) => ({
          ...activity,
          start_datetime: this.formatDateTimeForInput(activity.start_datetime),
          end_datetime: this.formatDateTimeForInput(activity.end_datetime),
        }));

        this.showEventModal = true;
      } catch (error) {
        console.error("Error loading event activities:", error);
        showToast("Error al cargar actividades del evento", "error");
        this.showEventModal = true; // Mostrar el modal aunque no se carguen las actividades
        this.currentEventActivities = [];
      }
    },

    // Ver actividades del evento
    viewActivities(event) {
      console.log("Viewing activities for event:", event.id);

      try {
        // Intentar cambiar la pestaña directamente
        const setActiveTab = (tabId) => {
          // Primero cambiar el hash
          window.location.hash = tabId;

          // Luego enviar el evento de carga
          setTimeout(() => {
            window.dispatchEvent(
              new CustomEvent("load-event-activities", {
                detail: {
                  eventId: event.id,
                  eventName: event.name,
                },
              })
            );
          }, 100);
        };

        // Ejecutar el cambio de pestaña
        setActiveTab("event_activities");

        console.log("Navegación iniciada a event_activities");
      } catch (error) {
        console.error("Error al navegar a actividades:", error);
        showToast("Error al navegar a las actividades", "error");

        // Como último recurso, intentar navegación directa
        window.location.hash = `event_activities?event_id=${event.id}`;
      }
    },

    // Preregistrar a una actividad
    async registerForActivity(activity) {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        // Obtener el ID del estudiante actual
        const studentId = this.getCurrentStudentId();
        if (!studentId) {
          throw new Error("No se pudo obtener el ID del estudiante");
        }

        const registrationData = {
          student_id: studentId,
          activity_id: activity.id,
        };

        const response = await fetch("/api/registrations/", {
          method: "POST",
          headers: window.getAuthHeaders(),
          body: JSON.stringify(registrationData),
        });

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }

          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al preregistrarse: ${response.status} ${response.statusText}`
          );
        }

        const data = await response.json();
        showToast("Preregistro realizado exitosamente", "success");

        if (!this.studentRegistrations.includes(activity.id)) {
          this.studentRegistrations.push(activity.id);
        }

        // Actualizar la actividad en la lista para reflejar que ya está registrada
        const activityIndex = this.currentEventActivities.findIndex(
          (a) => a.id === activity.id
        );
        if (activityIndex !== -1) {
          // Crear una nueva versión del objeto para asegurar la reactividad de Alpine.js
          const updatedActivity = {
            ...this.currentEventActivities[activityIndex],
            current_capacity:
              (this.currentEventActivities[activityIndex].current_capacity ||
                0) + 1,
          };
          // Reemplazar el objeto en el array
          this.currentEventActivities.splice(activityIndex, 1, updatedActivity);
        }
      } catch (error) {
        console.error("Error registering for activity:", error);
        showToast(
          error.message || "Error al preregistrarse a la actividad",
          "error"
        );
      }
    },

    // Verificar si ya está registrado en una actividad
    isActivityRegistered(activity) {
      return this.studentRegistrations.includes(activity.id);
    },

    // Verificar si se puede registrar en una actividad
    canRegisterForActivity(activity) {
      // Verificar si la actividad tiene cupo
      if (activity.max_capacity !== null) {
        return (activity.current_capacity || 0) < activity.max_capacity;
      }
      // Si no tiene cupo máximo, se puede registrar
      return true;
    },

    // Obtener el ID del estudiante actual
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

    // ✨ Verificar si es evento de un solo día
    isSingleDayEvent(event) {
      if (!event || !event.start_date || !event.end_date) return false;

      const startDate = new Date(event.start_date);
      const endDate = new Date(event.end_date);

      // Comparar solo la fecha (sin hora)
      return startDate.toDateString() === endDate.toDateString();
    },

    // ✨ Agrupar actividades por día
    groupActivitiesByDay(activities) {
      if (!activities || activities.length === 0) return {};

      const grouped = {};

      // Agrupar actividades por día
      activities.forEach((activity) => {
        const dateKey = activity.start_datetime.split("T")[0]; // YYYY-MM-DD
        if (!grouped[dateKey]) {
          grouped[dateKey] = {};
        }

        const activityType = activity.activity_type || "Otro";
        if (!grouped[dateKey][activityType]) {
          grouped[dateKey][activityType] = [];
        }

        grouped[dateKey][activityType].push(activity);
      });

      // Ordenar actividades dentro de cada grupo por hora de inicio (ASCENDENTE)
      Object.keys(grouped).forEach((date) => {
        Object.keys(grouped[date]).forEach((type) => {
          grouped[date][type].sort((a, b) => {
            return new Date(a.start_datetime) - new Date(b.start_datetime);
          });
        });
      });

      // ✨ ORDENAR LOS DÍAS POR FECHA (ASCENDENTE)
      const sortedDates = Object.keys(grouped).sort((a, b) => {
        return new Date(a) - new Date(b); // Orden ascendente por fecha
      });

      // Reorganizar el objeto agrupado con los días ordenados
      const sortedGrouped = {};
      sortedDates.forEach((date) => {
        sortedGrouped[date] = grouped[date];
      });

      return sortedGrouped;
    },

    // ✨ Obtener actividades ordenadas por hora (para eventos de un solo día)
    getSortedActivitiesByTime(activities) {
      if (!activities || activities.length === 0) return [];

      return [...activities].sort((a, b) => {
        return new Date(a.start_datetime) - new Date(b.start_datetime); // Orden ascendente
      });
    },

    formatOnlyDate(dateTimeString) {
      if (!dateTimeString) return "Sin fecha";
      const date = new Date(dateTimeString);
      return date.toLocaleDateString("es-ES", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      });
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
