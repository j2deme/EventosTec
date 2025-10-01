// app/static/js/admin/registrations.js
function registrationsManager() {
  return {
    // Estado
    registrations: [],
    activities: [],
    students: [],
    loading: false,
    saving: false,
    deleting: false,
    errorMessage: "",

    // Paginación
    currentPage: 1,
    totalPages: 1,
    totalItems: 0,
    perPage: 10,

    // Filtros
    filters: {
      search: "",
      activity_id: "",
      status: "",
    },

    // Modal
    showModal: false,
    showDeleteModal: false,
    showStatusDropdown: null,
    editMode: false,
    modalTitle: "Nuevo Registro",
    currentRegistration: {
      id: null,
      student_id: "",
      activity_id: "",
      status: "Registrado",
    },
    registrationToDelete: null,

    // Estadísticas
    stats: {
      total: 0,
      registrados: 0,
      confirmados: 0,
      asistio: 0,
      ausente: 0,
      cancelado: 0,
    },

    // Inicialización
    init() {
      this.loadRegistrations();
      this.loadActivities();
      this.loadStudents();
      this.loadStats();
      // Escuchar cambios en asistencias para mantener la UI sincronizada
      try {
        window.addEventListener("attendance:changed", (e) => {
          // Si el detalle viene con activity_id o student_id, recargar la lista
          try {
            const d = e && e.detail ? e.detail : {};
            // Si la lista tiene filtros, intentar recargar solo si el change afecta
            // a los filtros actuales; en caso de duda, recargar completamente.
            if (
              d.activity_id &&
              this.filters.activity_id &&
              String(d.activity_id) !== String(this.filters.activity_id)
            ) {
              // cambio en otra actividad -> recargar stats solamente
              this.loadStats();
            } else {
              // recargar registros visibles y stats
              this.loadRegistrations(this.currentPage);
            }
          } catch (err) {
            // fallback: recargar lista
            this.loadRegistrations(this.currentPage);
          }
        });
      } catch (e) {
        // ambiente sin DOM (tests)
      }
    },

    // Cargar registros
    async loadRegistrations(page = 1) {
      this.loading = true;
      this.errorMessage = "";

      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const params = new URLSearchParams({
          page: page,
          per_page: this.perPage,
        });
        if (this.filters.search) params.set("search", this.filters.search);
        if (this.filters.activity_id)
          params.set("activity_id", this.filters.activity_id);
        if (this.filters.status) params.set("status", this.filters.status);

        const response = await f(`/api/registrations?${params.toString()}`);
        if (!response || !response.ok)
          throw new Error(
            `Error al cargar registros: ${response && response.status}`
          );

        const data = await response.json();
        this.registrations = data.registrations || [];
        this.currentPage = data.page || 1;
        this.totalPages = data.pages || 1;
        this.totalItems = data.total || 0;

        // Si el servidor envía estadísticas agregadas, úsalas; si no, recalcúlalas localmente
        if (data.stats && typeof data.stats === "object") {
          try {
            this.stats = data.stats;
          } catch (e) {
            // fallback
            this.loadStats();
          }
        } else {
          // Actualizar estadísticas cuando se cargan registros (fallback)
          this.loadStats();
        }
      } catch (error) {
        console.error("Error loading registrations:", error);
        this.errorMessage = error.message || "Error al cargar registros";
        if (
          typeof window !== "undefined" &&
          typeof window.showToast === "function"
        ) {
          window.showToast("Error al cargar registros", "error");
        }
      } finally {
        this.loading = false;
      }
    },

    // Cargar actividades para los selectores
    async loadActivities() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) return;

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/activities?per_page=1000");
        if (response && response.ok) {
          const data = await response.json();
          this.activities = data.activities || [];
        }
      } catch (error) {
        console.error("Error loading activities:", error);
      }
    },

    // Cargar estudiantes para los selectores
    async loadStudents() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) return;

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/students?per_page=1000");
        if (response && response.ok) {
          const data = await response.json();
          this.students = data.students || [];
        }
      } catch (error) {
        console.error("Error loading students:", error);
      }
    },

    // Cargar estadísticas
    async loadStats() {
      try {
        // No hacemos fetchs si no hay token configurado (modo anónimo)
        const token = localStorage.getItem("authToken");
        if (!token) return;
        // Preferir estadísticas agregadas que el backend pueda enviar
        // (esto representa totales sobre la consulta completa, no solo la página).
        try {
          // Intentar descargar stats desde el endpoint de registro (sin paginar)
          // Formar parametros con los filtros actuales
          const params = new URLSearchParams();
          if (this.filters.search) params.set("search", this.filters.search);
          if (this.filters.activity_id)
            params.set("activity_id", this.filters.activity_id);
          if (this.filters.status) params.set("status", this.filters.status);

          const f =
            typeof window.safeFetch === "function" ? window.safeFetch : fetch;
          const res = await f(
            `/api/registrations?${params.toString()}&per_page=1`
          );
          if (res && res.ok) {
            const d = await res.json().catch(() => ({}));
            if (d && d.stats && typeof d.stats === "object") {
              this.stats = d.stats;
              return;
            }
          }
        } catch (e) {
          // ignore and fallback to local calculation
        }

        // Fallback: calcular estadísticas a partir de la página actual
        const stats = {
          total: this.registrations.length,
          registrados: 0,
          confirmados: 0,
          asistio: 0,
          ausente: 0,
          cancelado: 0,
        };

        this.registrations.forEach((reg) => {
          switch (reg.status) {
            case "Registrado":
              stats.registrados++;
              break;
            case "Confirmado":
              stats.confirmados++;
              break;
            case "Asistió":
              stats.asistio++;
              break;
            case "Ausente":
              stats.ausente++;
              break;
            case "Cancelado":
              stats.cancelado++;
              break;
          }
        });

        this.stats = stats;
      } catch (error) {
        console.error("Error loading stats:", error);
      }
    },

    // Navegación de páginas
    previousPage() {
      if (this.currentPage > 1) {
        this.currentPage--;
        this.loadRegistrations(this.currentPage);
      }
    },

    nextPage() {
      if (this.currentPage < this.totalPages) {
        this.currentPage++;
        this.loadRegistrations(this.currentPage);
      }
    },

    goToPage(page) {
      if (page >= 1 && page <= this.totalPages) {
        this.currentPage = page;
        this.loadRegistrations(page);
      }
    },

    getVisiblePages() {
      const pages = [];
      const start = Math.max(1, this.currentPage - 2);
      const end = Math.min(this.totalPages, this.currentPage + 2);

      for (let i = start; i <= end; i++) {
        pages.push(i);
      }

      return pages;
    },

    // Modal de crear/editar
    openCreateModal() {
      this.editMode = false;
      this.modalTitle = "Nuevo Registro";
      this.currentRegistration = {
        id: null,
        student_id: "",
        activity_id: "",
        status: "Registrado",
      };
      this.showModal = true;
      this.errorMessage = "";
    },

    openEditModal(registration) {
      this.editMode = true;
      this.modalTitle = "Editar Registro";
      this.currentRegistration = {
        id: registration.id,
        student_id: registration.student_id || registration.student?.id || "",
        activity_id:
          registration.activity_id || registration.activity?.id || "",
        status: registration.status || "Registrado",
      };
      this.showModal = true;
      this.errorMessage = "";
    },

    closeModal() {
      this.showModal = false;
      this.editMode = false;
      this.currentRegistration = {
        id: null,
        student_id: "",
        activity_id: "",
        status: "Registrado",
      };
      this.errorMessage = "";
    },

    // Guardar registro
    async saveRegistration() {
      if (this.editMode) {
        await this.updateRegistration();
      } else {
        await this.createRegistration();
      }
    },

    // Crear registro
    async createRegistration() {
      this.saving = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        const registrationData = {
          student_id: parseInt(this.currentRegistration.student_id),
          activity_id: parseInt(this.currentRegistration.activity_id),
        };

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/registrations", {
          method: "POST",
          body: JSON.stringify(registrationData),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al crear registro: ${response.status} ${response.statusText}`
          );
        }

        // Cerrar modal y recargar lista
        this.closeModal();
        this.loadRegistrations(this.currentPage);

        if (
          typeof window !== "undefined" &&
          typeof window.showToast === "function"
        ) {
          window.showToast("Registro creado exitosamente", "success");
        }
      } catch (error) {
        console.error("Error creating registration:", error);
        this.errorMessage = error.message || "Error al crear registro";
        if (
          typeof window !== "undefined" &&
          typeof window.showToast === "function"
        ) {
          window.showToast("Error al crear registro", "error");
        }
      } finally {
        this.saving = false;
      }
    },

    // Actualizar registro
    async updateRegistration() {
      this.saving = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        const registrationData = {
          student_id: parseInt(this.currentRegistration.student_id),
          activity_id: parseInt(this.currentRegistration.activity_id),
          status: this.currentRegistration.status,
        };

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(
          `/api/registrations/${this.currentRegistration.id}`,
          { method: "PUT", body: JSON.stringify(registrationData) }
        );

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al actualizar registro: ${response.status} ${response.statusText}`
          );
        }

        // Cerrar modal y recargar lista
        this.closeModal();
        this.loadRegistrations(this.currentPage);

        // Si la respuesta incluye un attendance (creado/actualizado) o el nuevo
        // estado es 'Asistió', despachar evento para que otros módulos (p.ej. lista
        // de asistencias) puedan refrescarse automáticamente.
        try {
          const body = await response.json().catch(() => ({}));
          const att = body && body.attendance ? body.attendance : null;
          const detail = att
            ? {
                attendance_id: att.id,
                activity_id: att.activity_id,
                student_id: att.student_id,
              }
            : {
                activity_id: registrationData.activity_id,
                student_id: registrationData.student_id,
              };
          try {
            window.dispatchEvent(
              new CustomEvent("attendance:changed", { detail })
            );
          } catch (e) {
            try {
              window.dispatchEvent(new Event("attendance:changed"));
            } catch (_) {}
          }
        } catch (e) {
          // ignore
        }
        if (
          typeof window !== "undefined" &&
          typeof window.showToast === "function"
        ) {
          window.showToast("Registro actualizado exitosamente", "success");
        }
      } catch (error) {
        console.error("Error updating registration:", error);
        this.errorMessage = error.message || "Error al actualizar registro";
        if (
          typeof window !== "undefined" &&
          typeof window.showToast === "function"
        ) {
          window.showToast("Error al actualizar registro", "error");
        }
      } finally {
        this.saving = false;
      }
    },

    // Cambiar estado de registro
    async changeRegistrationStatus(registrationId, newStatus) {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        const registration = this.registrations.find(
          (r) => r.id === registrationId
        );
        if (!registration) {
          throw new Error("Registro no encontrado");
        }

        const registrationData = {
          student_id: registration.student_id || registration.student?.id,
          activity_id: registration.activity_id || registration.activity?.id,
          status: newStatus,
        };

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(`/api/registrations/${registrationId}`, {
          method: "PUT",
          body: JSON.stringify(registrationData),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al cambiar estado: ${response.status} ${response.statusText}`
          );
        }

        // Recargar lista
        this.loadRegistrations(this.currentPage);

        // Notificar a otros módulos que la asistencia pudo haber cambiado
        try {
          const body = await response.json().catch(() => ({}));
          const att = body && body.attendance ? body.attendance : null;
          const detail = att
            ? {
                attendance_id: att.id,
                activity_id: att.activity_id,
                student_id: att.student_id,
              }
            : {
                activity_id: registration.activity_id,
                student_id: registration.student_id,
              };
          try {
            window.dispatchEvent(
              new CustomEvent("attendance:changed", { detail })
            );
          } catch (e) {
            try {
              window.dispatchEvent(new Event("attendance:changed"));
            } catch (_) {}
          }
        } catch (e) {
          // ignore
        }
        if (
          typeof window !== "undefined" &&
          typeof window.showToast === "function"
        ) {
          window.showToast(`Estado cambiado a: ${newStatus}`, "success");
        }
      } catch (error) {
        console.error("Error changing registration status:", error);
        if (
          typeof window !== "undefined" &&
          typeof window.showToast === "function"
        ) {
          window.showToast("Error al cambiar estado del registro", "error");
        }
      }
    },

    // Obtener transiciones de estado disponibles
    getAvailableStatusTransitions(currentStatus) {
      const transitions = {
        Registrado: ["Confirmado", "Cancelado"],
        Confirmado: ["Asistió", "Ausente", "Registrado"],
        Asistió: ["Confirmado"],
        Ausente: ["Confirmado"],
        Cancelado: ["Registrado"],
      };

      return transitions[currentStatus] || [];
    },

    // Modal de eliminación
    openDeleteModal(registration) {
      this.registrationToDelete = registration;
      this.showDeleteModal = true;
    },

    // Eliminar registro
    async deleteRegistration() {
      if (!this.registrationToDelete) return;

      this.deleting = true;

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(
          `/api/registrations/${this.registrationToDelete.id}`,
          { method: "DELETE" }
        );

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al eliminar registro: ${response.status} ${response.statusText}`
          );
        }

        // Cerrar modal y recargar lista
        this.showDeleteModal = false;
        this.registrationToDelete = null;
        this.loadRegistrations(this.currentPage);

        if (
          typeof window !== "undefined" &&
          typeof window.showToast === "function"
        ) {
          window.showToast("Registro eliminado exitosamente", "success");
        }
      } catch (error) {
        console.error("Error deleting registration:", error);
        if (
          typeof window !== "undefined" &&
          typeof window.showToast === "function"
        ) {
          window.showToast("Error al eliminar registro", "error");
        }
      } finally {
        this.deleting = false;
      }
    },

    // Formatear fecha (delegar a helper central cuando esté disponible)
    formatDate(dateString) {
      try {
        const helpers = require("../helpers/dateHelpers");
        return helpers.formatDate(dateString);
      } catch (e) {
        return window.formatDate
          ? window.formatDate(dateString)
          : dateString
          ? "N/A"
          : "N/A";
      }
    },
  };
}
// Hacer la función globalmente disponible en navegador
if (typeof window !== "undefined") {
  window.registrationsManager = registrationsManager;
}

// Exportar para Node/Jest (CommonJS)
if (typeof module !== "undefined" && module.exports) {
  module.exports = registrationsManager;
}
