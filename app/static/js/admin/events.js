function eventsManager() {
  return {
    // Estado
    events: [],
    loading: false,
    saving: false,
    deleting: false,
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
      status: "",
      sort: "created_at:desc",
    },

    // Modal
    showModal: false,
    showDeleteModal: false,
    editingEvent: null,
    currentEvent: {
      id: null,
      name: "",
      description: "",
      start_date: "",
      end_date: "",
      is_active: true,
    },
    eventToDelete: null,

    // Inicialización
    init() {
      this.showModal = false;
      this.showDeleteModal = false;
      this.eventToDelete = null;

      this.loadEvents();
    },

    // Cargar eventos
    async loadEvents(page = 1) {
      this.loading = true;
      this.errorMessage = "";

      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;

        const params = new URLSearchParams({
          page: page,
          per_page: 10,
        });
        if (this.filters.search) params.set("search", this.filters.search);
        if (this.filters.status) params.set("status", this.filters.status);
        if (this.filters.sort) params.set("sort", this.filters.sort);

        const response = await f(`/api/events?${params.toString()}`);
        if (!response || !response.ok) {
          throw new Error(
            `Error al cargar eventos: ${response && response.status}`
          );
        }

        const data = await response.json();

        this.events = (data.events || []).map((event) => ({
          ...event,
          start_date: this.formatDateTimeForInput(event.start_date),
          end_date: this.formatDateTimeForInput(event.end_date),
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
        console.error("Error loading events:", error);
        if (typeof showToast === "function")
          showToast("Error al cargar eventos", "error");
        this.errorMessage = error.message || "Error al cargar eventos";
      } finally {
        this.loading = false;
      }
    },

    // Crear evento
    async createEvent() {
      this.saving = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        // Preparar datos para enviar
        const eventData = {
          name: this.currentEvent.name,
          description: this.currentEvent.description,
          start_date: this.currentEvent.start_date,
          end_date: this.currentEvent.end_date,
          is_active: this.currentEvent.is_active,
        };

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/events", {
          method: "POST",
          body: JSON.stringify(eventData),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al crear evento: ${response.status} ${response.statusText}`
          );
        }

        const newEvent = await response.json();

        // Cerrar modal y recargar lista
        this.closeModal();
        this.loadEvents();

        window.dispatchEvent(
          new CustomEvent("event-created", {
            detail: {
              action: "create",
              eventId: newEvent.id,
            },
          })
        );

        showToast("Evento creado exitosamente", "success");
      } catch (error) {
        console.error("Error creating event:", error);
        showToast("Error al crear evento", "error");
        this.errorMessage = error.message || "Error al crear evento";
      } finally {
        this.saving = false;
      }
    },

    // Actualizar evento
    async updateEvent() {
      this.saving = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        // Preparar datos para enviar
        const eventData = {
          name: this.currentEvent.name,
          description: this.currentEvent.description,
          start_date: this.currentEvent.start_date,
          end_date: this.currentEvent.end_date,
          is_active: this.currentEvent.is_active,
        };

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(`/api/events/${this.currentEvent.id}`, {
          method: "PUT",
          body: JSON.stringify(eventData),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al actualizar evento: ${response.status} ${response.statusText}`
          );
        }

        const updatedEvent = await response.json();

        // Cerrar modal y recargar lista
        this.closeModal();
        this.loadEvents();

        window.dispatchEvent(
          new CustomEvent("event-updated", {
            detail: {
              action: "update",
              eventId: updatedEvent.id,
            },
          })
        );

        showToast("Evento actualizado exitosamente", "success");
      } catch (error) {
        console.error("Error updating event:", error);
        showToast("Error al actualizar evento", "error");
        this.errorMessage = error.message || "Error al actualizar evento";
      } finally {
        this.saving = false;
      }
    },

    // Eliminar evento
    async deleteEvent() {
      this.deleting = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        const eventId = this.eventToDelete.id;

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(`/api/events/${this.eventToDelete.id}`, {
          method: "DELETE",
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al eliminar evento: ${response.status} ${response.statusText}`
          );
        }

        // Cerrar modal y recargar lista
        this.showDeleteModal = false;
        this.eventToDelete = null;
        this.loadEvents();

        window.dispatchEvent(
          new CustomEvent("event-deleted", {
            detail: {
              action: "delete",
              eventId: eventId,
            },
          })
        );

        showToast("Evento eliminado exitosamente", "success");
      } catch (error) {
        console.error("Error deleting event:", error);
        showToast("Error al eliminar evento", "error");
        this.errorMessage = error.message || "Error al eliminar evento";
      } finally {
        this.deleting = false;
      }
    },

    // Abrir modal para crear
    openCreateModal() {
      this.editingEvent = false;
      this.currentEvent = {
        id: null,
        name: "",
        description: "",
        start_date: "",
        end_date: "",
        is_active: true,
      };
      this.showModal = true;
    },

    // Abrir modal para editar
    openEditModal(event) {
      this.editingEvent = true;
      // Copiar el evento para evitar mutaciones directas
      this.currentEvent = { ...event };
      this.showModal = true;
    },

    // Cerrar modal
    closeModal() {
      this.showModal = false;
      this.editingEvent = false;
      this.currentEvent = {
        id: null,
        name: "",
        description: "",
        start_date: "",
        end_date: "",
        is_active: true,
      };
    },

    // Confirmar eliminación
    confirmDelete(event) {
      this.eventToDelete = event;
      this.showDeleteModal = true;
    },

    // Guardar evento (crear o actualizar)
    saveEvent() {
      if (this.editingEvent) {
        this.updateEvent();
      } else {
        this.createEvent();
      }
    },

    // Cambiar página
    changePage(page) {
      if (page >= 1 && page <= this.pagination.last_page) {
        this.loadEvents(page);
      }
    },

    // Ver detalles del evento (opcional)
    viewEvent(event) {
      // Aquí podrías abrir un modal con más detalles
      // o redirigir a una página de detalle
      alert(`Ver detalles del evento: ${event.name}`);
    },

    // Delegar formateo de fechas a helpers centralizados
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
  };
}

// Hacer la función globalmente disponible en navegador
if (typeof window !== "undefined") {
  window.eventsManager = eventsManager;
}

// Exportar para Node/Jest (CommonJS)
if (typeof module !== "undefined" && module.exports) {
  module.exports = eventsManager;
}
