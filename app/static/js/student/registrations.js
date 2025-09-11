// static/js/student/registrations.js
console.log("Student Registrations Manager JS loaded");

function studentRegistrationsManager() {
  return {
    // Estado
    registrations: [],
    registrationsByDay: [], // ✨ Para agrupar preregistros por día
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

      // Escuchar evento para filtrar por evento (desde la vista de eventos)
      window.addEventListener("filter-activities-by-event", (event) => {
        // Podríamos implementar filtrado por evento si es necesario
        console.log("Filtrar por evento:", event.detail);
      });
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
          },
        }));

        // ✨ Agrupar preregistros por día
        this.groupRegistrationsByDay();

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

    // ✨ Agrupar preregistros por día (con manejo de actividades multídias como bloques diarios)
    groupRegistrationsByDay() {
      if (!this.registrations || this.registrations.length === 0) {
        this.registrationsByDay = [];
        return;
      }

      const grouped = {};

      this.registrations.forEach((registration) => {
        const activity = registration.activity;

        // ✨ Verificar si es una actividad multídias
        if (this.isMultiDayActivity(activity)) {
          // ✨ Generar bloques diarios para la actividad multídias
          const dailyBlocks = this.generateDailyBlocksForActivity(activity);

          // ✨ Agregar cada bloque diario al grupo correspondiente
          dailyBlocks.forEach((block) => {
            const dateKey = block.block_date; // YYYY-MM-DD
            if (!grouped[dateKey]) {
              grouped[dateKey] = [];
            }

            // Crear una "vista" del preregistro para este día específico
            const dailyRegistrationView = {
              ...registration,
              activity: {
                ...activity,
                // ✨ Sobrescribir fechas con las del bloque diario
                start_datetime: block.start_datetime,
                end_datetime: block.end_datetime,
                // ✨ Añadir información sobre el día actual dentro de la actividad multidia
                day_in_series: block.day_in_series,
                total_days: block.total_days,
                is_daily_block: true, // Marcar como bloque diario
              },
            };

            grouped[dateKey].push(dailyRegistrationView);
          });
        } else {
          // Actividad normal (un solo día)
          const dateKey = activity.start_datetime.split("T")[0]; // YYYY-MM-DD
          if (!grouped[dateKey]) {
            grouped[dateKey] = [];
          }

          grouped[dateKey].push(registration);
        }
      });

      // Ordenar preregistros dentro de cada grupo por hora de inicio (ASCENDENTE)
      Object.keys(grouped).forEach((date) => {
        grouped[date].sort((a, b) => {
          // ✨ Comparar solo las horas de inicio (ignorando la fecha)
          const timeA =
            new Date(a.activity.start_datetime).getHours() * 60 +
            new Date(a.activity.start_datetime).getMinutes();
          const timeB =
            new Date(b.activity.start_datetime).getHours() * 60 +
            new Date(b.activity.start_datetime).getMinutes();
          return timeA - timeB;
        });
      });

      // ✨ ORDENAR LOS DÍAS POR FECHA (ASCENDENTE)
      const sortedDateKeys = Object.keys(grouped).sort((a, b) => {
        return new Date(a) - new Date(b);
      });

      // Reorganizar el objeto agrupado con los días ordenados
      const sortedGrouped = {};
      sortedDateKeys.forEach((dateKey) => {
        sortedGrouped[dateKey] = grouped[dateKey];
      });

      // Convertir a array para el template
      this.registrationsByDay = Object.keys(sortedGrouped).map((date) => ({
        date: date,
        registrations: sortedGrouped[date],
      }));
    },

    // ✨ Verificar si una actividad es multídias
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

    // ✨ Generar bloques diarios para una actividad multídias
    generateDailyBlocksForActivity(activity) {
      if (!activity.start_datetime || !activity.end_datetime) return [];

      try {
        const startDate = new Date(activity.start_datetime);
        const endDate = new Date(activity.end_datetime);

        // Extraer horas y minutos del rango original
        const startTime = {
          hours: startDate.getHours(),
          minutes: startDate.getMinutes(),
        };
        const endTime = {
          hours: endDate.getHours(),
          minutes: endDate.getMinutes(),
        };

        // Generar fechas para cada día
        const datesInBetween = this.getDatesBetween(startDate, endDate);

        // Calcular el número total de días
        const totalDays = datesInBetween.length;

        // Crear bloques diarios
        const dailyBlocks = datesInBetween.map((dateObj, index) => {
          const dateStr = dateObj.toISOString().split("T")[0]; // YYYY-MM-DD

          // Crear fechas diarias con las horas del rango original
          const dailyStart = new Date(dateObj);
          dailyStart.setHours(startTime.hours, startTime.minutes, 0, 0);

          const dailyEnd = new Date(dateObj);
          dailyEnd.setHours(endTime.hours, endTime.minutes, 0, 0);

          return {
            block_date: dateStr,
            start_datetime: dailyStart.toISOString(),
            end_datetime: dailyEnd.toISOString(),
            day_in_series: index + 1,
            total_days: totalDays,
          };
        });

        return dailyBlocks;
      } catch (e) {
        console.error("Error generating daily blocks for activity:", e);
        return [];
      }
    },

    // ✨ Obtener todas las fechas entre dos fechas (inclusive)
    getDatesBetween(startDate, endDate) {
      const dates = [];
      const currentDate = new Date(startDate);
      const finalDate = new Date(endDate);

      currentDate.setHours(0, 0, 0, 0);
      finalDate.setHours(0, 0, 0, 0);

      while (currentDate <= finalDate) {
        dates.push(new Date(currentDate));
        currentDate.setDate(currentDate.getDate() + 1);
      }

      return dates;
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
        registration.status !== "Ausente" &&
        !registration.attended
      );
    },

    // Verificar si se puede re-registrar en una actividad
    canReRegisterForActivity(activity) {
      // Verificar si la actividad tiene cupo
      if (activity.max_capacity !== null) {
        return (activity.current_capacity || 0) < activity.max_capacity;
      }
      // Si no tiene cupo máximo, se puede registrar
      return true;
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

    // ✨ Re-registrar a una actividad (después de cancelar)
    async reRegisterForActivity(activity) {
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
              `Error al re-registrarse: ${response.status} ${response.statusText}`
          );
        }

        const data = await response.json();

        // ✨ Mostrar mensaje de éxito basado en la respuesta del backend
        if (data.message && data.message.includes("Reactivación")) {
          showToast(
            "Reactivación del registro realizada exitosamente",
            "success"
          );
        } else if (data.message && data.message.includes("Ya existe")) {
          showToast("Ya estás registrado en esta actividad", "info");
        } else {
          showToast("Registro actualizado exitosamente", "success");
        }

        // Recargar la lista de preregistros
        this.loadRegistrations();
      } catch (error) {
        console.error("Error registering for activity:", error);
        showToast(
          error.message || "Error al re-registrarse a la actividad",
          "error"
        );
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
