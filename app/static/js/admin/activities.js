// app/static/js/admin/activities.js
function activitiesManager() {
  return {
    // Estado
    activities: [],
    events: [], // Para el selector de eventos
    loading: false,
    saving: false,
    deleting: false,
    errorMessage: "",
    dateValidationError: "",
    minDate: "",
    maxDate: "",
    calculatedDuration: 0,

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
      event_id: "",
      activity_type: "",
      sort: "created_at:desc",
    },

    // Modal
    showModal: false,
    showDeleteModal: false,
    editingActivity: null,
    currentActivity: {
      id: null,
      event_id: "",
      department: "",
      name: "",
      description: "",
      start_datetime: "",
      end_datetime: "",
      duration_hours: null,
      activity_type: "",
      location: "",
      modality: "",
      requirements: "",
      max_capacity: null,
    },
    activityToDelete: null,

    // Inicialización
    init() {
      this.loadEvents(); // Cargar eventos para el selector
      this.loadActivities();
    },

    // Cargar actividades
    async loadActivities(page = 1) {
      this.loading = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        // Construir parámetros de consulta
        const params = new URLSearchParams({
          page: page,
          per_page: 10,
          ...(this.filters.search && { search: this.filters.search }),
          ...(this.filters.event_id && { event_id: this.filters.event_id }),
          ...(this.filters.activity_type && {
            activity_type: this.filters.activity_type,
          }),
          ...(this.filters.sort && { sort: this.filters.sort }),
        });

        const response = await fetch(`/api/activities?${params.toString()}`, {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
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

        // Actualizar paginación
        this.pagination = {
          current_page: data.current_page || 1,
          last_page: data.pages || 1,
          total: data.total || 0,
          from: (data.current_page - 1) * 10 + 1,
          to: Math.min(data.current_page * 10, data.total || 0),
          pages: Array.from({ length: data.pages || 1 }, (_, i) => i + 1),
        };
      } catch (error) {
        console.error("Error loading activities:", error);
        this.errorMessage = error.message || "Error al cargar actividades";
      } finally {
        this.loading = false;
      }
    },

    // Cargar eventos para el selector
    async loadEvents() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        const response = await fetch("/api/events/", {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          throw new Error(
            `Error al cargar eventos: ${response.status} ${response.statusText}`
          );
        }

        const data = await response.json();
        this.events = Array.isArray(data) ? data : data.events || [];
      } catch (error) {
        console.error("Error loading events:", error);
        this.errorMessage = error.message || "Error al cargar eventos";
      }
    },

    updateCalculatedDuration() {
      if (
        this.currentActivity.start_datetime &&
        this.currentActivity.end_datetime
      ) {
        const start = new Date(this.currentActivity.start_datetime);
        const end = new Date(this.currentActivity.end_datetime);

        if (!isNaN(start) && !isNaN(end) && start < end) {
          const diffMs = end - start;
          this.calculatedDuration = diffMs / (1000 * 60 * 60); // Convertir a horas
        } else {
          this.calculatedDuration = 0;
        }
      } else {
        this.calculatedDuration = 0;
      }
    },

    updateDateLimits() {
      /*console.log(
        "Updating date limits for event_id:",
        this.currentActivity.event_id
      );*/
      this.minDate = "";
      this.maxDate = "";

      if (this.currentActivity.event_id) {
        const selectedEvent = this.events.find(
          (e) => String(e.id) === String(this.currentActivity.event_id)
        );

        if (selectedEvent) {
          // Formatear las fechas del evento para los inputs datetime-local
          this.minDate = this.formatDateTimeForInput(selectedEvent.start_date);
          this.maxDate = this.formatDateTimeForInput(selectedEvent.end_date);
          console.log("Date limits set:", {
            min: this.minDate,
            max: this.maxDate,
          });
        }
      }
    },

    // Crear actividad
    async createActivity() {
      this.saving = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        // Preparar datos para enviar
        const activityData = {
          event_id: parseInt(this.currentActivity.event_id),
          department: this.currentActivity.department,
          name: this.currentActivity.name,
          description: this.currentActivity.description,
          start_datetime: this.currentActivity.start_datetime,
          end_datetime: this.currentActivity.end_datetime,
          ...(this.currentActivity.duration_hours !== null &&
            this.currentActivity.duration_hours !== "" && {
              duration_hours: parseFloat(this.currentActivity.duration_hours),
            }),
          activity_type: this.currentActivity.activity_type,
          location: this.currentActivity.location,
          modality: this.currentActivity.modality,
          requirements: this.currentActivity.requirements,
          max_capacity: this.currentActivity.max_capacity
            ? parseInt(this.currentActivity.max_capacity)
            : null,
        };

        const validationError = this.validateActivityDates(activityData);
        if (validationError) {
          throw new Error(validationError);
        }

        const response = await fetch("/api/activities/", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(activityData),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al crear actividad: ${response.status} ${response.statusText}`
          );
        }

        const newActivity = await response.json();

        // Cerrar modal y recargar lista
        this.closeModal();
        this.loadActivities();

        window.dispatchEvent(
          new CustomEvent("activity-created", {
            detail: {
              action: "created",
              eventId: newActivity.id,
            },
          })
        );

        // Mostrar mensaje de éxito
        alert("Actividad creada exitosamente");
      } catch (error) {
        console.error("Error creating activity:", error);
        this.errorMessage = error.message || "Error al crear actividad";
      } finally {
        this.saving = false;
      }
    },

    // Actualizar actividad
    async updateActivity() {
      this.saving = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        // Preparar datos para enviar
        const activityData = {
          event_id: parseInt(this.currentActivity.event_id),
          department: this.currentActivity.department,
          name: this.currentActivity.name,
          description: this.currentActivity.description,
          start_datetime: this.currentActivity.start_datetime,
          end_datetime: this.currentActivity.end_datetime,
          duration_hours: parseFloat(this.currentActivity.duration_hours),
          activity_type: this.currentActivity.activity_type,
          location: this.currentActivity.location,
          modality: this.currentActivity.modality,
          requirements: this.currentActivity.requirements,
          max_capacity: this.currentActivity.max_capacity
            ? parseInt(this.currentActivity.max_capacity)
            : null,
        };

        const validationError = this.validateActivityDates(activityData);
        if (validationError) {
          throw new Error(validationError);
        }

        const response = await fetch(
          `/api/activities/${this.currentActivity.id}`,
          {
            method: "PUT",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify(activityData),
          }
        );

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al actualizar actividad: ${response.status} ${response.statusText}`
          );
        }

        const updatedActivity = await response.json();

        // Cerrar modal y recargar lista
        this.closeModal();
        this.loadActivities();

        window.dispatchEvent(
          new CustomEvent("activity-updated", {
            detail: {
              action: "updated",
              eventId: updatedActivity.id,
            },
          })
        );

        // Mostrar mensaje de éxito
        alert("Actividad actualizada exitosamente");
      } catch (error) {
        console.error("Error updating activity:", error);
        this.errorMessage = error.message || "Error al actualizar actividad";
      } finally {
        this.saving = false;
      }
    },

    // Eliminar actividad
    async deleteActivity() {
      this.deleting = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        const response = await fetch(
          `/api/activities/${this.activityToDelete.id}`,
          {
            method: "DELETE",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          }
        );

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al eliminar actividad: ${response.status} ${response.statusText}`
          );
        }

        deletedId = this.activityToDelete.id;

        // Cerrar modal y recargar lista
        this.showDeleteModal = false;
        this.activityToDelete = null;
        this.loadActivities();

        window.dispatchEvent(
          new CustomEvent("activity-deleted", {
            detail: {
              action: "deleted",
              eventId: deletedId,
            },
          })
        );

        // Mostrar mensaje de éxito
        alert("Actividad eliminada exitosamente");
      } catch (error) {
        console.error("Error deleting activity:", error);
        this.errorMessage = error.message || "Error al eliminar actividad";
      } finally {
        this.deleting = false;
      }
    },

    // Abrir modal para crear
    openCreateModal() {
      this.calculatedDuration = 0;
      this.editingActivity = false;
      this.currentActivity = {
        id: null,
        event_id: "",
        department: "",
        name: "",
        description: "",
        start_datetime: "",
        end_datetime: "",
        duration_hours: 1.0,
        activity_type: "",
        location: "",
        modality: "",
        requirements: "",
        max_capacity: null,
      };
      this.minDate = "";
      this.maxDate = "";
      this.showModal = true;
    },

    // Abrir modal para editar
    openEditModal(activity) {
      this.editingActivity = true;
      // Copiar la actividad para evitar mutaciones directas
      this.currentActivity = { ...activity };
      this.updateDateLimits();
      this.showModal = true;
      this.dateValidationError = "";
      this.updateCalculatedDuration();
    },

    // Cerrar modal
    closeModal() {
      this.showModal = false;
      this.editingActivity = false;
      this.currentActivity = {
        id: null,
        event_id: "",
        department: "",
        name: "",
        description: "",
        start_datetime: "",
        end_datetime: "",
        duration_hours: 1.0,
        activity_type: "",
        location: "",
        modality: "",
        requirements: "",
        max_capacity: null,
      };
      this.dateValidationError = "";
      this.errorMessage = "";
      this.minDate = "";
      this.maxDate = "";
    },

    // Confirmar eliminación
    confirmDelete(activity) {
      this.activityToDelete = activity;
      this.showDeleteModal = true;
    },

    // Guardar actividad (crear o actualizar)
    saveActivity() {
      if (this.editingActivity) {
        this.updateActivity();
      } else {
        this.createActivity();
      }
    },

    // Cambiar página
    changePage(page) {
      if (page >= 1 && page <= this.pagination.last_page) {
        this.loadActivities(page);
      }
    },

    // Ver detalles de la actividad (opcional)
    viewActivity(activity) {
      // Aquí podrías abrir un modal con más detalles
      // o redirigir a una página de detalle
      alert(`Ver detalles de la actividad: ${activity.name}`);
    },

    validateActivityDates(activityData) {
      this.dateValidationError = ""; // Limpiar error anterior

      // Obtener el evento seleccionado
      const selectedEvent = this.events.find(
        (e) => String(e.id) === String(activityData.event_id)
      );
      if (!selectedEvent) {
        this.dateValidationError = "Por favor seleccione un evento válido";
        return this.dateValidationError;
      }

      // Convertir fechas a objetos Date
      const activityStart = new Date(activityData.start_datetime);
      const activityEnd = new Date(activityData.end_datetime);
      const eventStart = new Date(selectedEvent.start_date);
      const eventEnd = new Date(selectedEvent.end_date);

      // Validar que las fechas de la actividad estén dentro del rango del evento
      if (activityStart < eventStart) {
        this.dateValidationError = `La fecha de inicio de la actividad no puede ser anterior a la fecha de inicio del evento (${this.formatDateTime(
          eventStart
        )})`;
        return this.dateValidationError;
      }

      if (activityEnd > eventEnd) {
        this.dateValidationError = `La fecha de fin de la actividad no puede ser posterior a la fecha de fin del evento (${this.formatDateTime(
          eventEnd
        )})`;
        return this.dateValidationError;
      }

      // Validar que la fecha de inicio sea anterior a la fecha de fin
      if (activityStart >= activityEnd) {
        this.dateValidationError =
          "La fecha de inicio debe ser anterior a la fecha de fin";
        return this.dateValidationError;
      }

      return null; // Sin errores
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
  };
}

// Hacer la función globalmente disponible
window.activitiesManager = activitiesManager;
