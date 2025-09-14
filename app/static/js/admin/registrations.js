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
    },

    // Cargar registros
    async loadRegistrations(page = 1) {
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
          per_page: this.perPage,
          ...(this.filters.search && { search: this.filters.search }),
          ...(this.filters.activity_id && {
            activity_id: this.filters.activity_id,
          }),
          ...(this.filters.status && { status: this.filters.status }),
        });

        const response = await fetch(
          `/api/registrations?${params.toString()}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          }
        );

        if (!response.ok) {
          throw new Error(
            `Error al cargar registros: ${response.status} ${response.statusText}`
          );
        }

        const data = await response.json();

        this.registrations = data.registrations || [];
        this.currentPage = data.page || 1;
        this.totalPages = data.pages || 1;
        this.totalItems = data.total || 0;

        // Actualizar estadísticas cuando se cargan registros
        this.loadStats();
      } catch (error) {
        console.error("Error loading registrations:", error);
        this.errorMessage = error.message || "Error al cargar registros";
        showToast("Error al cargar registros", "error");
      } finally {
        this.loading = false;
      }
    },

    // Cargar actividades para los selectores
    async loadActivities() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) return;

        const response = await fetch("/api/activities?per_page=1000", {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (response.ok) {
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

        const response = await fetch("/api/students?per_page=1000", {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (response.ok) {
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
        const token = localStorage.getItem("authToken");
        if (!token) return;

        // Calcular estadísticas de los registros cargados
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

        const response = await fetch("/api/registrations", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
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

        showToast("Registro creado exitosamente", "success");
      } catch (error) {
        console.error("Error creating registration:", error);
        this.errorMessage = error.message || "Error al crear registro";
        showToast("Error al crear registro", "error");
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

        const response = await fetch(
          `/api/registrations/${this.currentRegistration.id}`,
          {
            method: "PUT",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify(registrationData),
          }
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

        showToast("Registro actualizado exitosamente", "success");
      } catch (error) {
        console.error("Error updating registration:", error);
        this.errorMessage = error.message || "Error al actualizar registro";
        showToast("Error al actualizar registro", "error");
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

        const response = await fetch(`/api/registrations/${registrationId}`, {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
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

        showToast(`Estado cambiado a: ${newStatus}`, "success");
      } catch (error) {
        console.error("Error changing registration status:", error);
        showToast("Error al cambiar estado del registro", "error");
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

        const response = await fetch(
          `/api/registrations/${this.registrationToDelete.id}`,
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
              `Error al eliminar registro: ${response.status} ${response.statusText}`
          );
        }

        // Cerrar modal y recargar lista
        this.showDeleteModal = false;
        this.registrationToDelete = null;
        this.loadRegistrations(this.currentPage);

        showToast("Registro eliminado exitosamente", "success");
      } catch (error) {
        console.error("Error deleting registration:", error);
        showToast("Error al eliminar registro", "error");
      } finally {
        this.deleting = false;
      }
    },

    // Formatear fecha
    formatDate(dateString) {
      if (!dateString) return "N/A";

      try {
        const date = new Date(dateString);
        return date.toLocaleDateString("es-ES", {
          year: "numeric",
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        });
      } catch (error) {
        return "Fecha inválida";
      }
    },
  };
}
