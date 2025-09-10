// static/js/student/event_activities.js
console.log("Student Event Activities Manager JS loaded");

function studentEventActivitiesManager() {
  return {
    // Estado
    currentEvent: {},
    activities: [],
    activitiesByDay: [],
    loading: false,
    loadingEvent: false,
    errorMessage: "",
    studentRegistrations: [],

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
      activity_type: "",
      sort: "start_datetime:asc",
    },

    // Inicialización
    async init() {
      console.log("Initializing student event activities manager...");

      this.isLoadingEvent = false;

      // Escuchar el evento personalizado para cargar actividades
      window.addEventListener("load-event-activities", async (event) => {
        console.log("Recibido evento load-event-activities:", event.detail);
        const { eventId, eventName } = event.detail;

        if (eventId) {
          // Crear un objeto de evento temporal para mostrar mientras se carga
          this.currentEvent = {
            id: eventId,
            name: eventName || "Cargando...",
          };

          // Cargar el evento completo y sus actividades
          await this.loadEvent(eventId);
          this.loadActivities();
        } else {
          this.errorMessage = "No se especificó un evento válido";
          showToast(this.errorMessage, "error");
          this.goToEvents();
        }
      });

      // Manejar la inicialización desde URL (por si se recarga la página)
      const urlParams = new URLSearchParams(
        window.location.hash.split("?")[1] || ""
      );
      const eventId = urlParams.get("event_id");

      if (eventId) {
        await this.loadEvent(eventId);
        this.loadActivities();
        this.loadStudentRegistrations();
      } else {
        this.goToEvents();
      }
    },

    goToEvents() {
      const dashboard = document.querySelector('[x-data*="studentDashboard"]');
      if (dashboard && dashboard.__x) {
        dashboard.__x.getUnobservedData().setActiveTab("events");
      }
    },

    // Cargar información del evento
    async loadEvent(eventId) {
      this.loadingEvent = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        const response = await fetch(`/api/events/${eventId}`, {
          headers: window.getAuthHeaders(),
        });

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(
            `Error al cargar evento: ${response.status} ${response.statusText}`
          );
        }

        const data = await response.json();
        this.currentEvent = {
          ...data.event,
          start_date: this.formatDateTimeForInput(data.event.start_date),
          end_date: this.formatDateTimeForInput(data.event.end_date),
        };
      } catch (error) {
        console.error("Error loading event:", error);
        this.errorMessage =
          error.message || "Error al cargar información del evento";
        showToast(this.errorMessage, "error");
      } finally {
        this.loadingEvent = false;
      }
    },

    // Cargar actividades
    async loadActivities(page = 1) {
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
          per_page: 20, // Más actividades por página para el cronograma
          event_id: this.currentEvent.id,
          ...(this.filters.search && { search: this.filters.search }),
          ...(this.filters.activity_type && {
            activity_type: this.filters.activity_type,
          }),
          ...(this.filters.sort && { sort: this.filters.sort }),
        });

        const response = await fetch(`/api/activities?${params.toString()}`, {
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
        this.activities = data.activities.map((activity) => ({
          ...activity,
          start_datetime: this.formatDateTimeForInput(activity.start_datetime),
          end_datetime: this.formatDateTimeForInput(activity.end_datetime),
        }));

        // ✨ Agrupar actividades por día
        this.groupActivitiesByDay();

        await this.loadStudentRegistrations();

        // Actualizar paginación
        this.pagination = {
          current_page: data.current_page || 1,
          last_page: data.pages || 1,
          total: data.total || 0,
          from: (data.current_page - 1) * 20 + 1,
          to: Math.min(data.current_page * 20, data.total || 0),
          pages: Array.from({ length: data.pages || 1 }, (_, i) => i + 1),
        };
      } catch (error) {
        console.error("Error loading activities:", error);
        this.errorMessage = error.message || "Error al cargar actividades";
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
          // Almacenar solo los IDs de las actividades registradas
          this.studentRegistrations = data.registrations.map(
            (r) => r.activity_id
          );
          console.log("Preregistros cargados:", this.studentRegistrations);

          // ✨ Actualizar la vista si ya tenemos actividades cargadas
          if (this.activities.length > 0) {
            this.groupActivitiesByDay();
          }
        }
      } catch (error) {
        console.error("Error loading student registrations:", error);
        // No es crítico, solo para la UI
      }
    },

    // ✨ Agrupar actividades por día
    groupActivitiesByDay() {
      const grouped = {};

      this.activities.forEach((activity) => {
        const dateKey = activity.start_datetime.split("T")[0]; // YYYY-MM-DD
        if (!grouped[dateKey]) {
          grouped[dateKey] = [];
        }
        grouped[dateKey].push(activity);
      });

      // Convertir a array y ordenar por fecha
      this.activitiesByDay = Object.keys(grouped)
        .sort()
        .map((date) => ({
          date: date,
          activities: grouped[date].sort((a, b) => {
            // Ordenar actividades dentro del día por hora de inicio
            return new Date(a.start_datetime) - new Date(b.start_datetime);
          }),
        }));
    },

    // Cambiar página
    changePage(page) {
      if (page >= 1 && page <= this.pagination.last_page) {
        this.loadActivities(page);
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

        // ✨ Actualizar visualmente el preregistro
        // Agregar a la lista de preregistros del estudiante
        if (!this.studentRegistrations.includes(activity.id)) {
          this.studentRegistrations.push(activity.id);
        }

        // ✨ Actualizar el cupo visualmente
        const activityIndex = this.activities.findIndex(
          (a) => a.id === activity.id
        );
        if (activityIndex !== -1) {
          // Crear una nueva versión del objeto para asegurar reactividad
          const updatedActivity = {
            ...this.activities[activityIndex],
            current_capacity:
              (this.activities[activityIndex].current_capacity || 0) + 1,
          };

          // Reemplazar el objeto en el array
          this.activities.splice(activityIndex, 1, updatedActivity);

          // ✨ Reagrupar actividades por día para actualizar la vista
          this.groupActivitiesByDay();
        }

        this.loadActivities(this.pagination.current_page);
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
      // Verificar si ya está registrado
      if (this.isActivityRegistered(activity)) {
        return false;
      }
      // Verificar si la actividad tiene cupo
      if (activity.max_capacity !== null) {
        return (activity.current_capacity || 0) < activity.max_capacity;
      }
      // Si no tiene cupo máximo, se puede registrar
      return true;
    },

    // Verificar si hay conflicto de horario (simplificado)
    hasScheduleConflict(activity) {
      // En una implementación completa, compararías con otras actividades registradas
      // Por ahora, retornamos false
      return false;
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

    // Volver a la lista de eventos
    goBack() {
      const dashboard = document.querySelector('[x-data*="studentDashboard"]');
      if (dashboard && dashboard.__x) {
        dashboard.__x.getUnobservedData().setActiveTab("events");
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

    // Formatear solo fecha para mostrar
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

    // Formatear solo hora para mostrar
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
window.studentEventActivitiesManager = studentEventActivitiesManager;
