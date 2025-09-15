// app/static/js/admin/activities.js
function activitiesManager() {
  return {
    // Estado
    activities: [],
    activityRelations: [],
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
      this.loadEvents();
      this.loadActivities();
      this.loadActivityRelations();
    },

    // Cargar actividades
    async loadActivities(page = 1) {
      this.loading = true;
      this.errorMessage = "";

      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;

        const params = new URLSearchParams({ page: page, per_page: 10 });
        if (this.filters.search) params.set("search", this.filters.search);
        if (this.filters.event_id)
          params.set("event_id", this.filters.event_id);
        if (this.filters.activity_type)
          params.set("activity_type", this.filters.activity_type);
        if (this.filters.sort) params.set("sort", this.filters.sort);

        const response = await f(`/api/activities?${params.toString()}`);
        if (!response || !response.ok)
          throw new Error(
            `Error al cargar actividades: ${response && response.status}`
          );

        const data = await response.json();

        this.activities = (data.activities || []).map((activity) => ({
          ...activity,
          start_datetime: this.formatDateTimeForInput(activity.start_datetime),
          end_datetime: this.formatDateTimeForInput(activity.end_datetime),
        }));

        const pages = data.pages || 1;
        const current = data.current_page || 1;
        const total = data.total || 0;

        this.pagination = {
          current_page: current,
          last_page: pages,
          total: total,
          from: (current - 1) * 10 + 1,
          to: Math.min(current * 10, total),
          pages: Array.from({ length: pages }, (_, i) => i + 1),
        };
      } catch (error) {
        console.error("Error loading activities:", error);
        showToast("Error al cargar actividades", "error");
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

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/events/");
        if (!response || !response.ok)
          throw new Error(
            `Error al cargar eventos: ${response && response.status}`
          );
        const data = await response.json();
        this.events = Array.isArray(data) ? data : data.events || [];
      } catch (error) {
        console.error("Error loading events:", error);
        showToast("Error al cargar eventos", "error");
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

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/activities/", {
          method: "POST",
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

        showToast("Actividad creada exitosamente", "success");
      } catch (error) {
        console.error("Error creating activity:", error);
        showToast("Error al crear actividad", "error");
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

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(`/api/activities/${this.currentActivity.id}`, {
          method: "PUT",
          body: JSON.stringify(activityData),
        });

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

        showToast("Actividad actualizada exitosamente", "success");
      } catch (error) {
        console.error("Error updating activity:", error);
        showToast("Error al actualizar actividad", "error");
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

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(
          `/api/activities/${this.activityToDelete.id}`,
          { method: "DELETE" }
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

        showToast("Actividad eliminada exitosamente", "success");
      } catch (error) {
        console.error("Error deleting activity:", error);
        showToast("Error al eliminar actividad", "error");
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

    // Actividades relacionadas
    relatedActivities: [],
    selectedToLink: "",
    async loadRelatedActivities(activityId) {
      try {
        this.relatedActivities = await this.getRelatedActivities(activityId);
      } catch (error) {
        this.relatedActivities = [];
      }
    },

    // Abrir modal para editar
    async openEditModal(activity) {
      this.editingActivity = true;
      // Copiar la actividad para evitar mutaciones directas
      this.currentActivity = { ...activity };
      this.updateDateLimits();
      this.showModal = true;
      this.dateValidationError = "";
      this.updateCalculatedDuration();
      if (activity.id) {
        await this.loadRelatedActivities(activity.id);
      }
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

    // Delegar formateo de fechas a helpers centralizados cuando estén disponibles
    formatDateTimeForInput(dateTimeString) {
      try {
        const helpers = require("../helpers/dateHelpers");
        return helpers.formatDateTimeForInput(dateTimeString);
      } catch (e) {
        return window.formatDateTimeForInput
          ? window.formatDateTimeForInput(dateTimeString)
          : "";
      }
    },

    formatDate(dateTimeString) {
      try {
        const helpers = require("../helpers/dateHelpers");
        return helpers.formatDate(dateTimeString);
      } catch (e) {
        return window.formatDate
          ? window.formatDate(dateTimeString)
          : "Sin fecha";
      }
    },

    formatDateTime(dateTimeString) {
      try {
        const helpers = require("../helpers/dateHelpers");
        return helpers.formatDateTime(dateTimeString);
      } catch (e) {
        return window.formatDateTime
          ? window.formatDateTime(dateTimeString)
          : "Sin fecha";
      }
    },

    // Consultar actividades relacionadas
    async getRelatedActivities(activityId) {
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const response = await f(`/api/activities/${activityId}/related`);
      if (!response.ok)
        throw new Error("Error al obtener actividades relacionadas");
      const data = await response.json();
      return data.related_activities || [];
    },

    // Enlazar actividad
    async linkActivity(activityId, relatedId) {
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const response = await f(`/api/activities/${activityId}/related`, {
        method: "POST",
        body: JSON.stringify({ related_activity_id: relatedId }),
      });
      if (!response || !response.ok)
        throw new Error("Error al enlazar actividades");
      if (typeof showToast === "function")
        showToast("Actividades enlazadas exitosamente", "success");
    },

    // Desenlazar actividad
    async unlinkActivity(activityId, relatedId) {
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const response = await f(
        `/api/activities/${activityId}/related/${relatedId}`,
        { method: "DELETE" }
      );
      if (!response || !response.ok)
        throw new Error("Error al desenlazar actividades");
      if (typeof showToast === "function")
        showToast("Actividades desenlazadas exitosamente", "success");
    },
    getAvailableActivities() {
      // Usar activityRelations para saber si una actividad está enlazada como A o B
      const linkedIds = new Set();
      this.activityRelations.forEach((act) => {
        if (
          (act.related_activities && act.related_activities.length > 0) ||
          (act.linked_by && act.linked_by.length > 0)
        ) {
          linkedIds.add(act.id);
        }
        if (Array.isArray(act.related_activities)) {
          act.related_activities.forEach((rel) => linkedIds.add(rel.id));
        }
        if (Array.isArray(act.linked_by)) {
          act.linked_by.forEach((rel) => linkedIds.add(rel.id));
        }
      });
      return this.activityRelations.filter(
        (a) =>
          a.event_id === this.currentActivity.event_id && !linkedIds.has(a.id)
      );
    },

    // Cargar relaciones de actividades (A y B)
    async loadActivityRelations() {
      const token = localStorage.getItem("authToken");
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const response = await f("/api/activities/relations");
      if (!response || !response.ok)
        throw new Error("Error al obtener relaciones");
      const data = await response.json();
      this.activityRelations = data.activities || [];
    },
  };
}

// Hacer la función globalmente disponible en navegador
if (typeof window !== "undefined") {
  window.activitiesManager = activitiesManager;
}

// Exportar para Node/Jest (CommonJS)
if (typeof module !== "undefined" && module.exports) {
  module.exports = activitiesManager;
}
