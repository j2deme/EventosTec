function studentRegistrationsManager() {
  return {
    registrations: [],
    loading: false,
    errorMessage: "",
    showCancelModal: false,
    registrationToCancel: null,

    pagination: {
      current_page: 1,
      last_page: 1,
      total: 0,
      from: 0,
      to: 0,
      pages: [],
    },

    filters: {
      search: "",
      status: "",
      sort: "registration_date:desc",
    },

    init() {
      this.loadRegistrations();
    },

    async loadRegistrations(page = 1) {
      this.loading = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        const studentId = this.getCurrentStudentId();
        if (!studentId) {
          throw new Error("No se pudo obtener el ID del estudiante");
        }

        const params = new URLSearchParams({
          page: page,
          per_page: 20,
          student_id: studentId,
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

        this.registrations = data.registrations.map((registration) => ({
          ...registration,
          registration_date: this.formatDateTimeForInput(
            registration.registration_date
          ),
          activity: {
            ...registration.activity,
            start_datetime: this.formatDateTimeForInput(
              registration.activity.start_datetime
            ),
            end_datetime: this.formatDateTimeForInput(
              registration.activity.end_datetime
            ),
            total_days: this.getTotalDays(registration.activity),
            day_in_series: this.getDayInSeries(registration.activity),
          },
        }));

        this.pagination = {
          current_page: data.current_page || 1,
          last_page: data.pages || 1,
          total: data.total || 0,
          from: (data.current_page - 1) * 20 + 1,
          to: Math.min(data.current_page * 20, data.total || 0),
          pages: Array.from({ length: data.pages || 1 }, (_, i) => i + 1),
        };
      } catch (error) {
        this.errorMessage = error.message || "Error al cargar preregistros";
        showToast(this.errorMessage, "error");
      } finally {
        this.loading = false;
      }
    },

    changePage(page) {
      if (page >= 1 && page <= this.pagination.last_page) {
        this.loadRegistrations(page);
      }
    },

    canCancelRegistration(registration) {
      return (
        registration.status !== "Asistió" &&
        registration.status !== "Cancelado" &&
        registration.status !== "Ausente" &&
        !registration.attended
      );
    },

    // NEW FUNCTION: Check if a canceled registration can be re-registered
    canReRegisterForActivity(activity) {
      // Check if activity exists and has valid dates
      if (!activity || !activity.start_datetime) {
        return false;
      }

      // Check if the activity hasn't started yet or is in the future
      const now = new Date();
      const activityStart = new Date(activity.start_datetime);

      // Allow re-registration if activity hasn't started yet
      return activityStart > now;
    },

    cancelRegistration(registration) {
      this.registrationToCancel = registration;
      this.showCancelModal = true;
    },

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

        this.showCancelModal = false;
        this.registrationToCancel = null;
        this.loadRegistrations();

        showToast("Preregistro cancelado exitosamente", "success");
      } catch (error) {
        showToast(error.message || "Error al cancelar preregistro", "error");
      }
    },

    // NEW FUNCTION: Re-register for a canceled activity
    async reRegisterForActivity(registration) {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        const studentId = this.getCurrentStudentId();
        if (!studentId) {
          throw new Error("No se pudo obtener el ID del estudiante");
        }

        const response = await fetch("/api/registrations", {
          method: "POST",
          headers: window.getAuthHeaders(),
          body: JSON.stringify({
            student_id: studentId,
            activity_id: registration.activity.id,
          }),
        });

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al volver a registrarse: ${response.status} ${response.statusText}`
          );
        }

        this.loadRegistrations();
        showToast("Registro reactivado exitosamente", "success");
      } catch (error) {
        showToast(error.message || "Error al volver a registrarse", "error");
      }
    },

    goToEvents() {
      const dashboard = document.querySelector('[x-data*="studentDashboard"]');
      if (dashboard && dashboard.__x) {
        dashboard.__x.getUnobservedData().setActiveTab("events");
      }
    },

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

    formatTime(dateTimeString) {
      if (!dateTimeString) return "--:--";
      const date = new Date(dateTimeString);
      return date.toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
      });
    },

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

    redirectToLogin() {
      localStorage.removeItem("authToken");
      localStorage.removeItem("userType");
      localStorage.removeItem("studentProfile");
      window.location.href = "/";
    },

    getCurrentStudentId() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) return null;

        const payload = JSON.parse(atob(token.split(".")[1]));
        return payload.sub;
      } catch (e) {
        return null;
      }
    },

    isMultiDayActivity(activity) {
      if (!activity.start_datetime || !activity.end_datetime) return false;

      try {
        const startDate = new Date(activity.start_datetime);
        const endDate = new Date(activity.end_datetime);

        // Comparar solo las fechas (sin horas)
        const startDay = new Date(
          startDate.getFullYear(),
          startDate.getMonth(),
          startDate.getDate()
        );
        const endDay = new Date(
          endDate.getFullYear(),
          endDate.getMonth(),
          endDate.getDate()
        );

        return startDay.getTime() !== endDay.getTime();
      } catch (e) {
        console.error("Error al verificar si es actividad multídias:", e);
        return false;
      }
    },

    getTotalDays(activity) {
      if (!activity.start_datetime || !activity.end_datetime) return 1;

      try {
        const startDate = new Date(activity.start_datetime);
        const endDate = new Date(activity.end_datetime);

        // Normalizar a medianoche para comparar solo fechas
        const startDay = new Date(
          startDate.getFullYear(),
          startDate.getMonth(),
          startDate.getDate()
        );
        const endDay = new Date(
          endDate.getFullYear(),
          endDate.getMonth(),
          endDate.getDate()
        );

        // Calcular la diferencia en días
        const timeDiff = endDay.getTime() - startDay.getTime();
        const totalDays = Math.floor(timeDiff / (1000 * 60 * 60 * 24)) + 1;

        return totalDays;
      } catch (e) {
        console.error("Error calculating total days:", e);
        return 1;
      }
    },

    getDayInSeries(activity) {
      if (!activity.start_datetime || !activity.end_datetime) return 1;

      try {
        const startDate = new Date(activity.start_datetime);
        const endDate = new Date(activity.end_datetime);
        const currentDate = new Date(activity.start_datetime); // Fecha actual es la de inicio por defecto

        // Normalizar a medianoche para comparar solo fechas
        const startDay = new Date(
          startDate.getFullYear(),
          startDate.getMonth(),
          startDate.getDate()
        );
        const currentDay = new Date(
          currentDate.getFullYear(),
          currentDate.getMonth(),
          currentDate.getDate()
        );

        // Calcular el número de días desde el inicio
        const timeDiff = currentDay.getTime() - startDay.getTime();
        const daysFromStart = Math.floor(timeDiff / (1000 * 60 * 60 * 24)) + 1;

        return daysFromStart;
      } catch (e) {
        console.error("Error calculating day in series:", e);
        return 1;
      }
    },
  };
}

window.studentRegistrationsManager = studentRegistrationsManager;
