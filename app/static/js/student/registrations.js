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

      // Auto-refresh when a registration is created elsewhere (other module or tab)
      // - CustomEvent: `window.dispatchEvent(new CustomEvent('registration-created'))`
      // - localStorage: `localStorage.setItem('registrationCreated', Date.now())` (triggers storage event in other tabs)
      // - BroadcastChannel: postMessage 'registration-created' on channel 'eventostec_channel'
      // Use a short debounce to avoid duplicate rapid reloads.
      this._refreshTimeout = null;

      this._onRegistrationCreated = () => {
        if (this._refreshTimeout) clearTimeout(this._refreshTimeout);
        this._refreshTimeout = setTimeout(() => this.loadRegistrations(), 300);
      };

      // Listen for a custom event within same tab
      window.addEventListener(
        "registration-created",
        this._onRegistrationCreated
      );

      // Listen for storage events from other tabs
      this._onStorage = (e) => {
        if (!e) return;
        if (e.key === "registrationCreated") {
          this._onRegistrationCreated();
        }
      };
      window.addEventListener("storage", this._onStorage);

      // BroadcastChannel for modern browsers (cross-tab)
      try {
        this._bc = new BroadcastChannel("eventostec_channel");
        this._bc.onmessage = (ev) => {
          if (!ev) return;
          if (ev.data === "registration-created") this._onRegistrationCreated();
        };
      } catch (e) {
        // Ignore if BroadcastChannel not supported
      }

      // Cleanup on page unload to avoid leaks (best-effort)
      window.addEventListener("beforeunload", () => {
        try {
          window.removeEventListener(
            "registration-created",
            this._onRegistrationCreated
          );
          window.removeEventListener("storage", this._onStorage);
          if (this._bc) this._bc.close();
        } catch (e) {}
      });
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
              registration.activity?.start_datetime
            ),
            end_datetime: this.formatDateTimeForInput(
              registration.activity?.end_datetime
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

    // Check if a canceled registration can be re-registered
    canReRegisterForActivity(activity) {
      if (!activity || !activity.start_datetime) return false;
      const now = new Date();
      const activityStart = new Date(activity.start_datetime);
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
            return `${pad(s.getDate())} - ${pad(e.getDate())}/${
              months[s.getMonth()]
            }/${s.getFullYear()}`;
          }
          return `${pad(s.getDate())}/${
            months[s.getMonth()]
          }/${s.getFullYear()} - ${pad(e.getDate())}/${
            months[e.getMonth()]
          }/${e.getFullYear()}`;
        }

        return `${pad(s.getDate())}/${months[s.getMonth()]}/${s.getFullYear()}`;
      } catch (e) {
        return "Sin fecha";
      }
    },

    // Convierte la lista de ponentes a una cadena legible incluyendo grado si existe
    speakersToString(activity) {
      try {
        if (!activity) return "";

        const ss = activity.speakersString;
        if (ss) {
          if (typeof ss === "string") return ss;
          if (Array.isArray(ss)) {
            return ss
              .map((it) => {
                if (!it) return null;
                if (typeof it === "string") return it;
                if (typeof it === "object")
                  return it.name || it.full_name || JSON.stringify(it);
                return String(it);
              })
              .filter(Boolean)
              .join(", ");
          }
          if (typeof ss === "object")
            return ss.name || ss.full_name || JSON.stringify(ss);
        }

        const s = activity.speakers;
        if (!s) return "";

        if (Array.isArray(s)) {
          return s
            .map((item) => {
              if (!item) return null;
              if (typeof item === "string") return item;
              if (typeof item === "object") {
                const name =
                  item.name ||
                  item.full_name ||
                  (item.first_name && item.last_name
                    ? `${item.first_name} ${item.last_name}`
                    : null);
                const degree =
                  item.degree ||
                  item.title ||
                  item.academic_degree ||
                  item.degree_title ||
                  null;
                if (name && degree) return `${degree} ${name}`;
                if (name) return name;
                return JSON.stringify(item);
              }
              return String(item);
            })
            .filter(Boolean)
            .join(", ");
        }

        if (typeof s === "string") return s;
        if (typeof s === "object") {
          const name =
            s.name ||
            s.full_name ||
            (s.first_name && s.last_name
              ? `${s.first_name} ${s.last_name}`
              : null);
          const degree =
            s.degree || s.title || s.academic_degree || s.degree_title || null;
          if (name && degree) return `${degree} ${name}`;
          if (name) return name;
          return JSON.stringify(s);
        }

        return "";
      } catch (e) {
        console.error("speakersToString error", e);
        return "";
      }
    },

    formatDateTime(dateTimeString) {
      return window.formatDateTime
        ? window.formatDateTime(dateTimeString)
        : "Sin fecha";
    },

    // Modal para ver detalles de la actividad (solo lectura)
    showActivityModal: false,
    selectedActivity: null,
    selectedActivityLoading: false,
    // Mantener el preregistro desde el que se abrió el modal para ajustar el contador
    selectedRegistration: null,

    async openActivityModal(registration) {
      this.selectedRegistration = registration || null;
      this.selectedActivity = registration?.activity || null;
      this.showActivityModal = true;

      // always try to fetch fresh activity details (to get updated counters)
      const activityId =
        this.selectedActivity?.id ||
        registration?.activity_id ||
        registration?.activity?.id;

      if (activityId) {
        this.selectedActivityLoading = true;
        try {
          const resp = await fetch(`/api/activities/${activityId}`, {
            headers: window.getAuthHeaders(),
          });
          if (resp.ok) {
            const payload = await resp.json();
            const activity = payload.activity || payload;
            if (activity) {
              // Normalize datetimes to input format if helper exists
              if (activity.start_datetime)
                activity.start_datetime = this.formatDateTimeForInput(
                  activity.start_datetime
                );
              if (activity.end_datetime)
                activity.end_datetime = this.formatDateTimeForInput(
                  activity.end_datetime
                );
              this.selectedActivity = Object.assign(
                {},
                this.selectedActivity || {},
                activity
              );
            }
          } else if (resp.status === 401) {
            this.redirectToLogin();
          } else {
            console.warn(
              "No se pudieron cargar detalles de la actividad",
              resp.status
            );
          }
        } catch (e) {
          console.error("Error fetching activity details", e);
        } finally {
          this.selectedActivityLoading = false;
        }
      }
    },

    closeActivityModal() {
      this.showActivityModal = false;
      this.selectedActivity = null;
      this.selectedActivityLoading = false;
      this.selectedRegistration = null;
    },

    // Devuelve una cadena para el cupo basada en los campos disponibles
    capacityText(activity) {
      if (!activity) return "No disponible";
      const reported =
        activity.current_capacity ??
        activity.current_registrations ??
        activity.current;

      // Si abrimos desde un preregistro activo, considerar al menos 1 participante
      const openedFromRegistration = !!(
        this.selectedRegistration &&
        (this.selectedRegistration.activity?.id ||
          this.selectedRegistration.activity_id) ==
          (activity.id || activity.activity_id)
      );

      let current;
      if (reported == null) {
        current = openedFromRegistration ? 1 : 0;
      } else {
        // Si el backend reporta 0 pero abrimos desde un preregistro activo, mostrar 1
        if (reported === 0 && openedFromRegistration) current = 1;
        else current = reported;
      }

      const max = activity.max_capacity ?? activity.capacity ?? null;
      if (max != null) return `${current}/${max}`;
      if (reported != null) return `${current}/∞`;
      return "No disponible";
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
      if (!activity?.start_datetime || !activity?.end_datetime) return false;

      try {
        const startDate = new Date(activity.start_datetime);
        const endDate = new Date(activity.end_datetime);

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
      if (!activity?.start_datetime || !activity?.end_datetime) return 1;
      try {
        const startDate = new Date(activity.start_datetime);
        const endDate = new Date(activity.end_datetime);
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
        const timeDiff = endDay.getTime() - startDay.getTime();
        return Math.floor(timeDiff / (1000 * 60 * 60 * 24)) + 1;
      } catch (e) {
        console.error("Error calculating total days:", e);
        return 1;
      }
    },

    getDayInSeries(activity) {
      if (!activity?.start_datetime || !activity?.end_datetime) return 1;
      try {
        const startDate = new Date(activity.start_datetime);
        const currentDate = new Date(activity.start_datetime);
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
        const timeDiff = currentDay.getTime() - startDay.getTime();
        return Math.floor(timeDiff / (1000 * 60 * 60 * 24)) + 1;
      } catch (e) {
        console.error("Error calculating day in series:", e);
        return 1;
      }
    },
  };
}

window.studentRegistrationsManager = studentRegistrationsManager;
