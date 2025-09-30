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
      return window.formatDateTimeForInput
        ? window.formatDateTimeForInput(dateTimeString)
        : "";
    },

    formatOnlyDate(dateTimeString) {
      return window.formatOnlyDate
        ? window.formatOnlyDate(dateTimeString)
        : "Sin fecha";
    },

    formatTime(dateTimeString) {
      if (!dateTimeString) return "--:--";
      // Reuse formatDateTime/time helpers if available
      if (window.formatDateTime) {
        const dt = new Date(dateTimeString);
        return dt.toLocaleTimeString("es-ES", {
          hour: "2-digit",
          minute: "2-digit",
        });
      }
      const date = new Date(dateTimeString);
      return date.toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
      });
    },

    // Devuelve fecha corta sin hora: DD mon YYYY (ej: 08 oct 2025)
    formatShortDateOnly(dateTimeString) {
      if (!dateTimeString) return "Sin fecha";
      try {
        const d = new Date(dateTimeString);
        if (isNaN(d.getTime())) return "Sin fecha";
        const pad = (n) => String(n).padStart(2, "0");
        const months = [
          "Ene",
          "Feb",
          "Mar",
          "Abr",
          "May",
          "Jun",
          "Jul",
          "Ago",
          "Sep",
          "Oct",
          "Nov",
          "Dic",
        ];
        return `${pad(d.getDate())}/${months[d.getMonth()]}/${d.getFullYear()}`;
      } catch (e) {
        return "Sin fecha";
      }
    },

    // Formatea la fecha de la actividad en versión reducida.
    // Si la actividad es multídia y ambas fechas están en el mismo mes, devuelve
    // "DD - DD / MM / YYYY". En caso contrario, devuelve "DD/MM/YYYY - DD/MM/YYYY".
    formatActivityDateShort(activity) {
      if (!activity || !activity.start_datetime) return "Sin fecha";
      try {
        const s = new Date(activity.start_datetime);
        const e = new Date(activity.end_datetime || activity.start_datetime);
        if (isNaN(s.getTime()) || isNaN(e.getTime())) return "Sin fecha";
        const pad = (n) => String(n).padStart(2, "0");
        const months = [
          "Ene",
          "Feb",
          "Mar",
          "Abr",
          "May",
          "Jun",
          "Jul",
          "Ago",
          "Sep",
          "Oct",
          "Nov",
          "Dic",
        ];

        const sameMonth =
          s.getFullYear() === e.getFullYear() && s.getMonth() === e.getMonth();

        if (this.isMultiDayActivity(activity)) {
          if (sameMonth) {
            // Ej: 08 - 10/Oct/2025
            return `${pad(s.getDate())} - ${pad(e.getDate())}/${
              months[s.getMonth()]
            }/${s.getFullYear()}`;
          }
          // Ej: 28/Sep/2025 - 02/Oct/2025
          return `${pad(s.getDate())}/${
            months[s.getMonth()]
          }/${s.getFullYear()} - ${pad(e.getDate())}/${
            months[e.getMonth()]
          }/${e.getFullYear()}`;
        }

        // Actividad de un solo día: devolver la fecha corta con nombre de mes abreviado
        return `${pad(s.getDate())}/${months[s.getMonth()]}/${s.getFullYear()}`;
      } catch (e) {
        return "Sin fecha";
      }
    },

    formatDateTime(dateTimeString) {
      return window.formatDateTime
        ? window.formatDateTime(dateTimeString)
        : "Sin fecha";
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
