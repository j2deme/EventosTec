// static/js/student/event_activities.js
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
    // Evitar múltiples peticiones concurrentes para la misma actividad
    inflightRegistrations: new Set(),

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
      // Inicializar estado (suppress verbose logs)
      this.loadingEvent = false;
      this.errorMessage = "";

      // Escuchar el evento personalizado para cargar actividades
      const loadActivitiesListener = async (event) => {
        const { eventId, eventName } = event.detail;

        if (eventId) {
          // Crear un objeto de evento temporal para mostrar mientras se carga
          this.currentEvent = {
            id: eventId,
            name: eventName || "Cargando...",
          };

          // Cargar el evento completo y sus actividades
          await this.loadEvent(eventId);
          // Cargar todas las actividades en una sola carga
          await this.loadActivities();
        } else {
          this.errorMessage = "No se especificó un evento válido";
          showToast(this.errorMessage, "error");
          this.goToEvents();
        }
      };

      window.addEventListener("load-event-activities", loadActivitiesListener);

      this._loadActivitiesListener = loadActivitiesListener;

      // Manejar la inicialización desde URL (por si se recarga la página)
      const urlParams = new URLSearchParams(
        window.location.hash.split("?")[1] || ""
      );
      const eventId = urlParams.get("event_id");

      if (eventId) {
        await this.loadEvent(eventId);
        // Cargar todas las actividades en una sola carga
        await this.loadActivities();
        // loadActivities ya invoca loadStudentRegistrations()
      } else {
        this.goBack();
      }
    },

    goToEvents() {
      const dashboard = document.querySelector('[x-data*="studentDashboard"]');
      if (dashboard && dashboard.__x) {
        dashboard.__x.getUnobservedData().setActiveTab("events");
      }
    },

    // ✨ Corregida función goBack para usar goToEvents
    goBack() {
      try {
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
          dashboard.__x.getUnobservedData().setActiveTab("events");
        } else {
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
          window.location.href = "/dashboard/student";
        }
      }
    },

    // Cargar información del evento
    async loadEvent(eventId) {
      this.loadingEvent = true;
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

        // Construir parámetros de consulta - usar un per_page alto para mostrar todas las actividades
        const params = new URLSearchParams({
          page: page,
          per_page: 2000, // Cargar todas las actividades en una sola página
          event_id: this.currentEvent.id,
          ...(this.filters.search && { search: this.filters.search }),
          ...(this.filters.activity_type && {
            activity_type: this.filters.activity_type,
          }),
          ...(this.filters.sort && { sort: this.filters.sort }),
        });

        // Add for_student flag so backend can exclude forbidden activity types
        params.append("for_student", "true");
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

        // Defensive client-side filter: ensure forbidden activity types are removed
        const filtered = (data.activities || []).filter(
          (a) => String(a.activity_type).toLowerCase() !== "magistral"
        );

        this.originalActivities = filtered.map((activity) => ({
          ...activity,
          start_datetime: this.formatDateTimeForInput(activity.start_datetime),
          end_datetime: this.formatDateTimeForInput(activity.end_datetime),
        }));

        // Mapear actividades y formatear fechas (para uso general)
        // Copiar array de actividades (ya filtradas)
        this.activities = this.originalActivities.map((activity) => ({
          ...activity,
        }));

        // ✨ Agrupar actividades por día para presentación visual
        this.groupActivitiesByDayForDisplay();

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

          if (!Array.isArray(this.studentRegistrations)) {
            this.studentRegistrations = [];
          }
          // Solo necesitamos los IDs de las actividades registradas
          this.studentRegistrations = data.registrations.map(
            (r) => r.activity_id
          );
          // Reagrupar la vista usando la función que mantiene las vistas
          // diarias expandidas para actividades multídia (incluye
          // day_in_series/total_days). Antes se usaba groupActivitiesByDay()
          // lo cual eliminaba esas propiedades y provocaba que la plantilla
          // mostrara el botón en todas las sesiones.
          this.groupActivitiesByDayForDisplay();
        }
      } catch (error) {
        console.error("Error loading student registrations:", error);
        if (!Array.isArray(this.studentRegistrations)) {
          this.studentRegistrations = [];
        }
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
      // ✨ Obtener la actividad original para verificación precisa
      const originalActivity = this.getOriginalActivityById(activity.id);

      try {
        // ✨ Verificar si es una actividad multídias usando los datos originales
        if (originalActivity && this.isMultiDayActivity(originalActivity)) {
          const confirmed = await this.showMultiDayConfirmation(
            originalActivity
          );
          if (!confirmed) {
            // Usuario canceló la confirmación
            return;
          }
        }

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

        // Evitar doble envío para la misma actividad
        if (this.inflightRegistrations.has(activity.id)) {
          console.warn("Registro ya en curso para actividad", activity.id);
          return;
        }
        this.inflightRegistrations.add(activity.id);

        const registrationData = {
          student_id: studentId,
          activity_id: activity.id, // Usar el ID de la actividad original
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

        try {
          // Intentar encontrar el manager de preregistros y recargar
          const registrationsManagerElement = document.querySelector(
            '[x-data*="studentRegistrationsManager"]'
          );
          if (registrationsManagerElement && registrationsManagerElement.__x) {
            const registrationsManager =
              registrationsManagerElement.__x.getUnobservedData();
            // Solo recargar si ya se han cargado preregistros alguna vez
            if (typeof registrationsManager.loadRegistrations === "function") {
              // Recargar en la página actual o primera página
              await registrationsManager.loadRegistrations(
                registrationsManager.pagination.current_page
              );
            }
          }
        } catch (refreshError) {
          console.warn(
            "No se pudo actualizar automáticamente la lista de preregistros:",
            refreshError
          );
          // No es crítico, solo para la UX
        }

        try {
          if (!this.studentRegistrations.includes(activity.id)) {
            this.studentRegistrations.push(activity.id);
          }

          // Actualizar el array fuente que usa la vista (originalActivities)
          const origIndex = this.originalActivities.findIndex(
            (a) => a.id === activity.id
          );
          if (origIndex !== -1) {
            const newCount =
              (this.originalActivities[origIndex].current_capacity || 0) + 1;
            this.originalActivities.splice(origIndex, 1, {
              ...this.originalActivities[origIndex],
              current_capacity: newCount,
            });
          }

          // También actualizar el array visible (activities) por consistencia
          const activityIndex = this.activities.findIndex(
            (a) => a.id === activity.id
          );
          if (activityIndex !== -1) {
            const updatedActivity = {
              ...this.activities[activityIndex],
              current_capacity:
                (this.activities[activityIndex].current_capacity || 0) + 1,
            };
            this.activities.splice(activityIndex, 1, updatedActivity);
          }

          // Reagrupar la vista para que use los datos actualizados
          this.groupActivitiesByDayForDisplay();
        } finally {
          // Limpiar estado inflight
          this.inflightRegistrations.delete(activity.id);
        }
      } catch (error) {
        console.error("Error registering for activity:", error);
        showToast(
          error.message || "Error al preregistrarse a la actividad",
          "error"
        );
        // Asegurar limpieza de inflight si hubo error antes del finally
        try {
          this.inflightRegistrations.delete(activity.id);
        } catch (e) {
          // noop
        }
      }
    },

    // ✨ Agrupar actividades por día SOLO para presentación visual (sin modificar actividades originales)
    groupActivitiesByDayForDisplay() {
      if (!this.originalActivities || this.originalActivities.length === 0) {
        this.activitiesByDay = [];
        return;
      }

      const grouped = {};

      this.originalActivities.forEach((activity) => {
        const startDate = new Date(activity.start_datetime);
        const endDate = new Date(activity.end_datetime);

        // ✨ Para actividades multídias: crear entradas para cada día
        if (this.isMultiDayActivity(activity)) {
          // Generar fechas para cada día
          const datesInBetween = this.getDatesBetween(startDate, endDate);

          datesInBetween.forEach((dateObj) => {
            const dateStr = dateObj.toISOString().split("T")[0]; // YYYY-MM-DD

            if (!grouped[dateStr]) {
              grouped[dateStr] = [];
            }

            // Crear una "vista" de la actividad para este día específico
            const dailyActivityView = {
              ...activity,
              _expanded_for_date: dateStr,
              day_in_series: this.getDayInSeries(
                activity.start_datetime,
                activity.end_datetime,
                dateStr
              ),
              total_days: this.getTotalDays(
                activity.start_datetime,
                activity.end_datetime
              ),
              is_expanded_view: true,
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

    // Verificar si ya está registrado en una actividad
    isActivityRegistered(activity) {
      // ✨ Asegurar que studentRegistrations sea un array
      if (!Array.isArray(this.studentRegistrations)) {
        console.warn(
          "studentRegistrations no es un array en isActivityRegistered"
        );
        this.studentRegistrations = [];
        return false;
      }

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

    showMultiDayConfirmation(activity) {
      // Crear un elemento modal de confirmación
      const modalHtml = `
        <div id="multiday-confirm-modal" class="fixed inset-0 z-50 overflow-y-auto" style="display: none;">
          <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div class="fixed inset-0 transition-opacity" aria-hidden="true">
              <div class="absolute inset-0 bg-gray-500 opacity-75"></div>
            </div>
            
            <span class="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
            
            <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div class="sm:flex sm:items-start">
                  <div class="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-yellow-100 sm:mx-0 sm:h-10 sm:w-10">
                    <i class="ti ti-alert-triangle text-yellow-600"></i>
                  </div>
                  <div class="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                    <h3 class="text-lg leading-6 font-medium text-gray-900">Confirmar Preregistro</h3>
                    <div class="mt-2">
                      <p class="text-sm text-gray-500">
                        La actividad <strong>${
                          activity.name
                        }</strong> es una actividad multídias.
                      </p>
                      <p class="mt-2 text-sm text-gray-500">
                        Esto significa que tendrás sesiones los días:
                      </p>
                      <div class="mt-2 p-2 bg-gray-50 rounded-md">
                        <p class="text-xs font-medium text-gray-700">
                          Del ${this.formatOnlyDate(activity.start_datetime)} 
                          al ${this.formatOnlyDate(activity.end_datetime)}
                        </p>
                      </div>
                      <p class="mt-3 text-sm text-gray-500">
                        ¿Estás seguro de que deseas preregistrarte a todas las sesiones de esta actividad?
                      </p>
                    </div>
                  </div>
                </div>
              </div>
              <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                <button type="button" 
                        id="confirm-multiday-register"
                        class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:ml-3 sm:w-auto sm:text-sm">
                  Sí, preregistrarme
                </button>
                <button type="button" 
                        id="cancel-multiday-register"
                        class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm">
                  Cancelar
                </button>
              </div>
            </div>
          </div>
        </div>
      `;

      // Agregar el modal al body
      document.body.insertAdjacentHTML("beforeend", modalHtml);

      // Mostrar el modal
      const modal = document.getElementById("multiday-confirm-modal");
      modal.style.display = "block";

      // Retornar una promesa que se resuelve cuando el usuario confirma o cancela
      return new Promise((resolve) => {
        const confirmBtn = document.getElementById("confirm-multiday-register");
        const cancelBtn = document.getElementById("cancel-multiday-register");
        const closeModal = () => {
          modal.remove();
          resolve(false);
        };

        confirmBtn.onclick = () => {
          modal.remove();
          resolve(true);
        };

        cancelBtn.onclick = closeModal;

        // También cerrar con Escape
        document.onkeydown = (e) => {
          if (e.key === "Escape") {
            closeModal();
          }
        };
      });
    },

    // Delegar formateo de fechas/hora a los helpers globales
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
      const dt = new Date(dateTimeString);
      return dt.toLocaleTimeString("es-ES", {
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
      // Usar los datos originales para la verificación
      const originalActivity = this.originalActivities.find(
        (a) => a.id === activity.id
      );
      const activityToCheck = originalActivity || activity; // Fallback al activity pasado si no se encuentra el original

      if (!activityToCheck.start_datetime || !activityToCheck.end_datetime) {
        return false;
      }

      try {
        const startDate = new Date(activityToCheck.start_datetime);
        const endDate = new Date(activityToCheck.end_datetime);

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

        const isMultiDay = startDay.getTime() !== endDay.getTime();

        return isMultiDay;
      } catch (e) {
        console.error("Error al verificar si es actividad multídias:", e);
        return false;
      }
    },

    // ✨ Obtener actividad original por ID
    getOriginalActivityById(activityId) {
      return this.originalActivities.find((a) => a.id === activityId);
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

    async refreshCurrentEventActivities() {
      if (!this.currentEvent || !this.currentEvent.id) {
        return false;
      }

      try {
        await this.loadActivities();
        return true;
      } catch (error) {
        console.error("❌ Error refrescando actividades del evento:", error);
        return false;
      }
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
