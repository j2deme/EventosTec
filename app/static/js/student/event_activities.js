// static/js/student/event_activities.js
console.log("Student Event Activities Manager JS loaded");

function studentEventActivitiesManager() {
  return {
    // Estado
    currentEvent: {},
    activities: [],
    activitiesByDay: [],
    loading: false,
    loadingEvent: false,
    errorMessage: "",
    studentRegistrations: [],

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
      activity_type: "",
      sort: "start_datetime:asc",
    },

    // Inicialización
    async init() {
      console.log("Initializing student event activities manager...");

      // Inicializar estado
      this.loadingEvent = false;
      this.errorMessage = "";

      // Escuchar el evento personalizado para cargar actividades
      const loadActivitiesListener = async (event) => {
        console.log("✅ Recibido evento load-event-activities:", event.detail);
        const { eventId, eventName } = event.detail;

        if (eventId) {
          // Crear un objeto de evento temporal para mostrar mientras se carga
          this.currentEvent = {
            id: eventId,
            name: eventName || "Cargando...",
          };

          // Cargar el evento completo y sus actividades
          await this.loadEvent(eventId);
          this.loadActivities();
        } else {
          this.errorMessage = "No se especificó un evento válido";
          showToast(this.errorMessage, "error");
          this.goToEvents();
        }
      };

      window.addEventListener("load-event-activities", loadActivitiesListener);

      // ✨ Guardar referencia al listener para poder removerlo si es necesario
      this._loadActivitiesListener = loadActivitiesListener;

      // Manejar la inicialización desde URL (por si se recarga la página)
      const urlParams = new URLSearchParams(
        window.location.hash.split("?")[1] || ""
      );
      const eventId = urlParams.get("event_id");

      if (eventId) {
        await this.loadEvent(eventId);
        this.loadActivities();
        this.loadStudentRegistrations();
      } else {
        // ✨ No redirigir inmediatamente, esperar a que se cargue el evento
        console.log("No hay eventId en la URL, esperando evento personalizado");
        this.goBack();
      }
    },

    // ✨ Corregida función para volver a la lista de eventos
    goToEvents() {
      const dashboard = document.querySelector('[x-data*="studentDashboard"]');
      if (dashboard && dashboard.__x) {
        dashboard.__x.getUnobservedData().setActiveTab("events");
      }
    },

    // ✨ Corregida función goBack para usar goToEvents
    goBack() {
      console.log("Intentando regresar a la lista de eventos...");

      try {
        // ✨ Método más robusto para encontrar y cambiar la pestaña
        let dashboard = null;

        // Intentar encontrar el dashboard de varias maneras
        const possibleSelectors = [
          '[x-data*="studentDashboard"]',
          '[x-data^="studentDashboard"]',
          "[x-data]",
        ];

        for (let selector of possibleSelectors) {
          const elements = document.querySelectorAll(selector);
          for (let element of elements) {
            if (
              element.__x &&
              typeof element.__x.getUnobservedData === "function"
            ) {
              const data = element.__x.getUnobservedData();
              if (data && typeof data.setActiveTab === "function") {
                dashboard = element;
                break;
              }
            }
          }
          if (dashboard) break;
        }

        if (dashboard && dashboard.__x) {
          console.log("Dashboard encontrado, cambiando pestaña a events");
          dashboard.__x.getUnobservedData().setActiveTab("events");
        } else {
          // ✨ Si no encontramos el dashboard, intentar navegación directa
          console.log("Dashboard no encontrado, intentando navegación directa");
          window.location.hash = "events";
        }
      } catch (error) {
        console.error("Error al regresar a eventos:", error);
        // ✨ Como último recurso, intentar navegación directa
        try {
          window.location.hash = "events";
        } catch (fallbackError) {
          console.error("Error en navegación de fallback:", fallbackError);
          // Si todo falla, recargar la página en la pestaña de eventos
          window.location.href = "/dashboard/student#events";
        }
      }
    },

    // Cargar información del evento
    async loadEvent(eventId) {
      this.loadingEvent = true; // ✨ Corregido nombre de variable
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        const response = await fetch(`/api/events/${eventId}`, {
          headers: window.getAuthHeaders(),
        });

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(
            `Error al cargar evento: ${response.status} ${response.statusText}`
          );
        }

        const data = await response.json();
        this.currentEvent = {
          ...data.event,
          start_date: this.formatDateTimeForInput(data.event.start_date),
          end_date: this.formatDateTimeForInput(data.event.end_date),
        };
        console.log("Evento cargado:", this.currentEvent);
      } catch (error) {
        console.error("Error loading event:", error);
        this.errorMessage =
          error.message || "Error al cargar información del evento";
        showToast(this.errorMessage, "error");
      } finally {
        this.loadingEvent = false; // ✨ Corregido nombre de variable
      }
    },

    // Cargar actividades
    async loadActivities(page = 1) {
      this.loading = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        // Construir parámetros de consulta
        const params = new URLSearchParams({
          page: page,
          per_page: 20, // Más actividades por página para el cronograma
          event_id: this.currentEvent.id,
          ...(this.filters.search && { search: this.filters.search }),
          ...(this.filters.activity_type && {
            activity_type: this.filters.activity_type,
          }),
          ...(this.filters.sort && { sort: this.filters.sort }),
        });

        const response = await fetch(`/api/activities?${params.toString()}`, {
          headers: window.getAuthHeaders(),
        });

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
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

        // ✨ Agrupar actividades por día
        this.groupActivitiesByDay();

        // Cargar preregistros del estudiante
        await this.loadStudentRegistrations();

        // Actualizar paginación
        this.pagination = {
          current_page: data.current_page || 1,
          last_page: data.pages || 1,
          total: data.total || 0,
          from: (data.current_page - 1) * 20 + 1,
          to: Math.min(data.current_page * 20, data.total || 0),
          pages: Array.from({ length: data.pages || 1 }, (_, i) => i + 1),
        };
      } catch (error) {
        console.error("Error loading activities:", error);
        this.errorMessage = error.message || "Error al cargar actividades";
        showToast(this.errorMessage, "error");
      } finally {
        this.loading = false;
      }
    },

    async loadStudentRegistrations() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) return;

        const studentId = this.getCurrentStudentId();
        if (!studentId) return;

        const response = await fetch(
          `/api/registrations?student_id=${studentId}`,
          {
            headers: window.getAuthHeaders(),
          }
        );

        if (response.ok) {
          const data = await response.json();
          // Solo necesitamos los IDs de las actividades registradas
          this.studentRegistrations = data.registrations.map(
            (r) => r.activity_id
          );
          console.log("Preregistros cargados:", this.studentRegistrations);
        }
      } catch (error) {
        console.error("Error loading student registrations:", error);
        // No es crítico, solo para la UI
      }
    },

    // ✨ Agrupar actividades por día
    groupActivitiesByDay() {
      const grouped = {};

      this.activities.forEach((activity) => {
        const dateKey = activity.start_datetime.split("T")[0]; // YYYY-MM-DD
        if (!grouped[dateKey]) {
          grouped[dateKey] = [];
        }
        grouped[dateKey].push(activity);
      });

      // Convertir a array y ordenar por fecha
      this.activitiesByDay = Object.keys(grouped)
        .sort()
        .map((date) => ({
          date: date,
          activities: grouped[date].sort((a, b) => {
            // Ordenar actividades dentro del día por hora de inicio
            return new Date(a.start_datetime) - new Date(b.start_datetime);
          }),
        }));
    },

    // Cambiar página
    changePage(page) {
      if (page >= 1 && page <= this.pagination.last_page) {
        this.loadActivities(page);
      }
    },

    // Preregistrar a una actividad
    async registerForActivity(activity) {
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
              `Error al preregistrarse: ${response.status} ${response.statusText}`
          );
        }

        const data = await response.json();
        showToast("Preregistro realizado exitosamente", "success");

        // Actualizar la actividad en la lista para reflejar que ya está registrada
        if (!this.studentRegistrations.includes(activity.id)) {
          this.studentRegistrations.push(activity.id);
        }

        // Actualizar el cupo visualmente
        const activityIndex = this.activities.findIndex(
          (a) => a.id === activity.id
        );
        if (activityIndex !== -1) {
          // Crear una nueva versión del objeto para asegurar la reactividad
          const updatedActivity = {
            ...this.activities[activityIndex],
            current_capacity:
              (this.activities[activityIndex].current_capacity || 0) + 1,
          };
          // Reemplazar el objeto en el array
          this.activities.splice(activityIndex, 1, updatedActivity);

          // Reagrupar actividades por día para actualizar la vista
          this.groupActivitiesByDay();
        }
      } catch (error) {
        console.error("Error registering for activity:", error);
        showToast(
          error.message || "Error al preregistrarse a la actividad",
          "error"
        );
      }
    },

    // Verificar si ya está registrado en una actividad
    isActivityRegistered(activity) {
      return this.studentRegistrations.includes(activity.id);
    },

    // Verificar si se puede registrar en una actividad
    canRegisterForActivity(activity) {
      // Verificar si ya está registrado
      if (this.isActivityRegistered(activity)) {
        return false;
      }
      // Verificar si la actividad tiene cupo
      if (activity.max_capacity !== null) {
        return (activity.current_capacity || 0) < activity.max_capacity;
      }
      // Si no tiene cupo máximo, se puede registrar
      return true;
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

    // Redirigir al login
    redirectToLogin() {
      localStorage.removeItem("authToken");
      localStorage.removeItem("userType");
      localStorage.removeItem("studentProfile");
      window.location.href = "/";
    },

    // ✨ Verificar si una actividad es multídias
    isMultiDayActivity(activity) {
      if (!activity.start_datetime || !activity.end_datetime) return false;

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
    },

    // ✨ Verificar si es evento de un solo día
    isSingleDayEvent(event) {
      if (!event || !event.start_date || !event.end_date) return true; // Por defecto asumir single day si no hay datos

      try {
        const startDate = new Date(event.start_date);
        const endDate = new Date(event.end_date);

        // Comparar solo la fecha (sin hora)
        return startDate.toDateString() === endDate.toDateString();
      } catch (e) {
        console.error("Error al verificar si es evento de un solo día:", e);
        return true; // Por defecto asumir single day si hay error
      }
    },

    // ✨ Agrupar actividades por día para el cronograma
    groupActivitiesByDayForTimeline(activities) {
      if (!activities || activities.length === 0) return {};

      const grouped = {};

      activities.forEach((activity) => {
        const startDate = new Date(activity.start_datetime);
        const endDate = new Date(activity.end_datetime);

        // ✨ Para actividades multídias: crear entradas para cada día
        if (this.isMultiDayActivity(activity)) {
          // Generar fechas para cada día
          const datesInBetween = this.getDatesBetween(startDate, endDate);

          datesInBetween.forEach((dateStr) => {
            if (!grouped[dateStr]) {
              grouped[dateStr] = [];
            }

            // Crear una "vista" de la actividad para este día específico
            const dailyActivityView = {
              ...activity,
              _expanded_for_date: dateStr,
              // ✨ Añadir información sobre el día actual dentro de la actividad multidia
              day_in_series: this.getDayInSeries(startDate, endDate, dateStr),
              total_days: this.getTotalDays(startDate, endDate),
            };

            grouped[dateStr].push(dailyActivityView);
          });
        } else {
          // Actividad normal (un solo día)
          const dateKey = activity.start_datetime.split("T")[0]; // YYYY-MM-DD
          if (!grouped[dateKey]) {
            grouped[dateKey] = [];
          }

          grouped[dateKey].push(activity);
        }
      });

      // Ordenar actividades dentro de cada grupo por hora de inicio (ASCENDENTE)
      Object.keys(grouped).forEach((date) => {
        grouped[date].sort((a, b) => {
          // ✨ Comparar solo las horas de inicio (ignorando la fecha)
          const timeA =
            new Date(a.start_datetime).getHours() * 60 +
            new Date(a.start_datetime).getMinutes();
          const timeB =
            new Date(b.start_datetime).getHours() * 60 +
            new Date(b.start_datetime).getMinutes();
          return timeA - timeB;
        });
      });

      // ✨ ORDENAR LOS DÍAS POR FECHA (ASCENDENTE)
      const sortedDateKeys = Object.keys(grouped).sort((a, b) => {
        return new Date(a) - new Date(b); // Orden ascendente por fecha
      });

      // Reorganizar el objeto agrupado con los días ordenados
      const sortedGrouped = {};
      sortedDateKeys.forEach((dateKey) => {
        sortedGrouped[dateKey] = grouped[dateKey];
      });

      return sortedGrouped;
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

    // ✨ Obtener el número del día actual dentro de la serie multidia (1/3, 2/3, etc.)
    getDayInSeries(startDate, endDate, currentDay) {
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
      const currentDayDate = new Date(currentDay);

      // Calcular el número de días desde el inicio
      const daysFromStart =
        Math.floor((currentDayDate - startDay) / (1000 * 60 * 60 * 24)) + 1;

      return daysFromStart;
    },

    // ✨ Obtener el rango de horas diario para una actividad multídias en un día específico
    getDailyRangeForMultiDayActivity(
      activityStart,
      activityEnd,
      targetDateStr
    ) {
      const activityStartDate = new Date(activityStart);
      const activityEndDate = new Date(activityEnd);
      const targetDate = new Date(targetDateStr);

      // Normalizar fechas a medianoche para comparación
      const targetDay = new Date(
        targetDate.getFullYear(),
        targetDate.getMonth(),
        targetDate.getDate()
      );
      const activityStartDay = new Date(
        activityStartDate.getFullYear(),
        activityStartDate.getMonth(),
        activityStartDate.getDate()
      );
      const activityEndDay = new Date(
        activityEndDate.getFullYear(),
        activityEndDate.getMonth(),
        activityEndDate.getDate()
      );

      // Extraer horas y minutos del rango original
      const startTime = {
        hours: activityStartDate.getHours(),
        minutes: activityStartDate.getMinutes(),
      };
      const endTime = {
        hours: activityEndDate.getHours(),
        minutes: activityEndDate.getMinutes(),
      };

      let dailyStart, dailyEnd;

      // Crear fechas diarias con las horas del rango original
      if (targetDay.getTime() === activityStartDay.getTime()) {
        // Primer día: usar hora de inicio original
        dailyStart = new Date(targetDay);
        dailyStart.setHours(startTime.hours, startTime.minutes, 0, 0);
      } else {
        // Días intermedios: usar hora de inicio del rango
        dailyStart = new Date(targetDay);
        dailyStart.setHours(startTime.hours, startTime.minutes, 0, 0);
      }

      if (targetDay.getTime() === activityEndDay.getTime()) {
        // Último día: usar hora de fin original
        dailyEnd = new Date(targetDay);
        dailyEnd.setHours(endTime.hours, endTime.minutes, 0, 0);
      } else {
        // Días intermedios: usar hora de fin del rango
        dailyEnd = new Date(targetDay);
        dailyEnd.setHours(endTime.hours, endTime.minutes, 0, 0);
      }

      return {
        start: dailyStart,
        end: dailyEnd,
      };
    },

    // ✨ Obtener el número del día actual dentro de la serie multidia (1/3, 2/3, etc.)
    getDayInSeries(activityStart, activityEnd, currentDateStr) {
      const activityStartDate = new Date(activityStart);
      const activityEndDate = new Date(activityEnd);
      const currentDate = new Date(currentDateStr);

      const activityStartDay = new Date(
        activityStartDate.getFullYear(),
        activityStartDate.getMonth(),
        activityStartDate.getDate()
      );
      const activityEndDay = new Date(
        activityEndDate.getFullYear(),
        activityEndDate.getMonth(),
        activityEndDate.getDate()
      );
      const currentDay = new Date(
        currentDate.getFullYear(),
        currentDate.getMonth(),
        currentDate.getDate()
      );

      // Calcular el número de días desde el inicio
      const timeDiff = currentDay.getTime() - activityStartDay.getTime();
      const daysFromStart = Math.floor(timeDiff / (1000 * 60 * 60 * 24)) + 1;

      return daysFromStart;
    },

    // ✨ Obtener el total de días de la actividad multidia
    getTotalDays(activityStart, activityEnd) {
      const activityStartDate = new Date(activityStart);
      const activityEndDate = new Date(activityEnd);

      const activityStartDay = new Date(
        activityStartDate.getFullYear(),
        activityStartDate.getMonth(),
        activityStartDate.getDate()
      );
      const activityEndDay = new Date(
        activityEndDate.getFullYear(),
        activityEndDate.getMonth(),
        activityEndDate.getDate()
      );

      // Calcular la diferencia en días
      const timeDiff = activityEndDay.getTime() - activityStartDay.getTime();
      const totalDays = Math.floor(timeDiff / (1000 * 60 * 60 * 24)) + 1;

      return totalDays;
    },

    // ✨ Obtener actividades ordenadas por hora (para eventos de un solo día)
    getSortedActivitiesByTime(activities) {
      if (!activities || activities.length === 0) return [];

      return [...activities].sort((a, b) => {
        return new Date(a.start_datetime) - new Date(b.start_datetime); // Orden ascendente
      });
    },

    // ✨ Agrupar actividades por día (con manejo de actividades multídias como bloques diarios)
    groupActivitiesByDay() {
      if (!this.activities || this.activities.length === 0) {
        this.activitiesByDay = [];
        return;
      }

      const grouped = {};

      this.activities.forEach((activity) => {
        const startDate = new Date(activity.start_datetime);
        const endDate = new Date(activity.end_datetime);

        // ✨ Para actividades multídias: crear entradas para cada día con bloques diarios
        if (this.isMultiDayActivity(activity)) {
          // Generar fechas para cada día
          const datesInBetween = this.getDatesBetween(startDate, endDate);

          datesInBetween.forEach((dateObj) => {
            const dateStr = dateObj.toISOString().split("T")[0]; // YYYY-MM-DD

            if (!grouped[dateStr]) {
              grouped[dateStr] = [];
            }

            // Obtener el rango diario para esta actividad en este día específico
            const dailyRange = this.getDailyRangeForMultiDayActivity(
              activity.start_datetime,
              activity.end_datetime,
              dateStr
            );

            // Crear una "vista" de la actividad para este día específico con bloques diarios
            const dailyActivityView = {
              ...activity,
              _expanded_for_date: dateStr,
              // ✨ Usar el rango diario en lugar del rango general
              start_datetime: dailyRange.start.toISOString(),
              end_datetime: dailyRange.end.toISOString(),
              // ✨ Añadir información sobre el día actual dentro de la actividad multidia
              day_in_series: this.getDayInSeries(
                activity.start_datetime,
                activity.end_datetime,
                dateStr
              ),
              total_days: this.getTotalDays(
                activity.start_datetime,
                activity.end_datetime
              ),
              // ✨ Marcar como actividad expandida
              is_expanded_multiday: true,
            };

            grouped[dateStr].push(dailyActivityView);
          });
        } else {
          // Actividad normal (un solo día)
          const dateKey = activity.start_datetime.split("T")[0]; // YYYY-MM-DD
          if (!grouped[dateKey]) {
            grouped[dateKey] = [];
          }

          grouped[dateKey].push(activity);
        }
      });

      // Ordenar actividades dentro de cada grupo por hora de inicio (ASCENDENTE)
      Object.keys(grouped).forEach((date) => {
        grouped[date].sort((a, b) => {
          // ✨ Comparar solo las horas de inicio (ignorando la fecha)
          const timeA =
            new Date(a.start_datetime).getHours() * 60 +
            new Date(a.start_datetime).getMinutes();
          const timeB =
            new Date(b.start_datetime).getHours() * 60 +
            new Date(b.start_datetime).getMinutes();
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
      this.activitiesByDay = Object.keys(sortedGrouped).map((date) => ({
        date: date,
        activities: sortedGrouped[date],
      }));
    },

    // ✨ Formatear solo fecha para mostrar
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

    // ✨ Formatear solo hora para mostrar
    formatTime(dateTimeString) {
      if (!dateTimeString) return "--:--";
      const date = new Date(dateTimeString);
      return date.toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
      });
    },
  };
}

// Hacer la función globalmente disponible
window.studentEventActivitiesManager = studentEventActivitiesManager;
