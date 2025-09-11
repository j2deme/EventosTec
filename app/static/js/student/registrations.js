// static/js/student/registrations.js
console.log("Student Registrations Manager JS loaded");

function studentRegistrationsManager() {
  return {
    // Estado
    registrations: [],
    loading: false,
    errorMessage: "",
    showCancelModal: false,
    registrationToCancel: null,

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
      sort: "registration_date:desc",
    },

    // Inicialización
    init() {
      console.log("Initializing student registrations manager...");
      this.loadRegistrations();

      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible" && this.isActiveTab()) {
          console.log("🔄 Refrescando al volver a la pestaña...");
          this.loadRegistrations(this.pagination.current_page);
        }
      });

      // ✨ Refrescar al enfocar la ventana (opcional)
      window.addEventListener("focus", () => {
        if (this.isActiveTab()) {
          console.log("🔄 Refrescando al enfocar la ventana...");
          this.loadRegistrations(this.pagination.current_page);
        }
      });

      // Escuchar evento para filtrar por evento (desde la vista de eventos)
      window.addEventListener("filter-activities-by-event", (event) => {
        // Podríamos implementar filtrado por evento si es necesario
        console.log("Filtrar por evento:", event.detail);
      });
    },

    isActiveTab() {
      try {
        // ✨ Usar selectores más específicos y robustos
        const possibleSelectors = [
          '[x-data*="studentDashboard"]', // Selector original
          '[x-data^="studentDashboard"]', // Comienza con studentDashboard
          '[x-data*="studentDashboard()"]', // Incluye studentDashboard()
          '[x-data="studentDashboard()"]', // Exactamente studentDashboard()
          '[data-x-data*="studentDashboard"]', // En caso de que sea data-x-data
        ];

        let dashboard = null;
        let dashboardData = null;

        // Intentar encontrar el dashboard con diferentes selectores
        for (let selector of possibleSelectors) {
          const elements = document.querySelectorAll(selector);
          for (let element of elements) {
            if (
              element.__x &&
              typeof element.__x.getUnobservedData === "function"
            ) {
              const data = element.__x.getUnobservedData();
              if (data && typeof data.activeTab !== "undefined") {
                dashboard = element;
                dashboardData = data;
                console.log(
                  `✅ Dashboard encontrado con selector: ${selector}`
                );
                break;
              }
            }
          }
          if (dashboard) break;
        }

        // Si encontramos el dashboard, verificar la pestaña activa
        if (dashboard && dashboardData) {
          const isActive = dashboardData.activeTab === "registrations";
          console.log(
            `📊 Pestaña actual: ${dashboardData.activeTab}, ¿Es 'registrations'? ${isActive}`
          );
          return isActive;
        }

        // ✨ Fallback: verificar el hash de la URL
        console.log("🔄 Verificando fallback con hash de URL");
        const hash = window.location.hash.substring(1);
        return hash === "registrations";
      } catch (e) {
        console.warn("⚠️ No se pudo determinar si es pestaña activa:", e);
        // ✨ Fallback adicional: verificar hash de URL
        try {
          const hash = window.location.hash.substring(1);
          return hash === "registrations";
        } catch (fallbackError) {
          console.error("💥 Error en fallback de isActiveTab:", fallbackError);
          return true; // Por defecto, asumir que sí para no perder actualizaciones
        }
      }
    },

    // Cargar preregistros
    async loadRegistrations(page = 1) {
      this.loading = true;
      this.errorMessage = "";

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

        // Construir parámetros de consulta
        const params = new URLSearchParams({
          page: page,
          per_page: 10,
          student_id: studentId, // Filtrar por el estudiante actual
          ...(this.filters.search && { search: this.filters.search }),
          ...(this.filters.status && { status: this.filters.status }),
          ...(this.filters.sort && { sort: this.filters.sort }),
        });

        const response = await fetch(
          `/api/registrations?${params.toString()}`,
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
            `Error al cargar preregistros: ${response.status} ${response.statusText}`
          );
        }

        const data = await response.json();

        // Mapear preregistros y formatear fechas
        this.registrations = data.registrations.map((registration) => {
          // Asegurar que 'activity' exista
          const activity = registration.activity || {};

          return {
            ...registration,
            registration_date: registration.registration_date
              ? this.formatDateTimeForInput(registration.registration_date)
              : "",
            activity: {
              ...activity,
              // Solo formatear si las fechas existen
              start_datetime: activity.start_datetime
                ? this.formatDateTimeForInput(activity.start_datetime)
                : "",
              end_datetime: activity.end_datetime
                ? this.formatDateTimeForInput(activity.end_datetime)
                : "",
            },
          };
        });

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
        console.error("Error loading registrations:", error);
        this.errorMessage = error.message || "Error al cargar preregistros";
        showToast(this.errorMessage, "error");
      } finally {
        this.loading = false;
      }
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

    // Cambiar página
    changePage(page) {
      if (page >= 1 && page <= this.pagination.last_page) {
        this.loadRegistrations(page);
      }
    },

    // Verificar si se puede cancelar un preregistro
    canCancelRegistration(registration) {
      // Solo se puede cancelar si no ha asistido y no está ya cancelado
      return (
        registration.status !== "Asistió" &&
        registration.status !== "Cancelado" &&
        !registration.attended
      );
    },

    // Solicitar cancelación de preregistro
    cancelRegistration(registration) {
      this.registrationToCancel = registration;
      this.showCancelModal = true;
    },

    // Confirmar cancelación de preregistro
    async confirmCancelRegistration() {
      if (!this.registrationToCancel) return;

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        const response = await fetch(
          `/api/registrations/${this.registrationToCancel.id}`,
          {
            method: "DELETE",
            headers: window.getAuthHeaders(),
          }
        );

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al cancelar preregistro: ${response.status} ${response.statusText}`
          );
        }

        // Cerrar modal y recargar lista
        this.showCancelModal = false;
        this.registrationToCancel = null;
        this.loadRegistrations();

        showToast("Preregistro cancelado exitosamente", "success");
      } catch (error) {
        console.error("Error canceling registration:", error);
        showToast(error.message || "Error al cancelar preregistro", "error");
      }
    },

    // Ir a la vista de eventos
    goToEvents() {
      // Cambiar a la pestaña de eventos
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
window.studentRegistrationsManager = studentRegistrationsManager;
