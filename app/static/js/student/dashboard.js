// static/js/student/dashboard.js
// startup logs removed to avoid noisy console output in production

function studentDashboard() {
  return {
    // Estado del componente
    sidebarOpen: false,
    activeTab: "overview",
    isLoading: false,
    errorMessage: "",

    // Datos del estudiante
    studentName: "",
    studentControlNumber: "",
    studentCareer: "",
    studentEmail: "",

    // Menú de navegación
    menuItems: [
      { id: "overview", name: "Resumen", icon: "ti ti-layout-dashboard" },
      { id: "events", name: "Eventos", icon: "ti ti-calendar-event" },
      {
        id: "event_activities",
        name: "Actividades",
        icon: "ti ti-book",
        hidden: true,
      },
      { id: "registrations", name: "Mis Preregistros", icon: "ti ti-bookmark" },
      { id: "profile", name: "Mi Perfil", icon: "ti ti-user" },
    ],

    // Inicialización
    init() {
      // initialization (verbose logs removed)

      // Verificar autenticación
      if (!window.checkAuthAndRedirect()) {
        // Auth helper handles redirection; suppress verbose log
        return;
      }

      // Establecer pestaña inicial
      this.setInitialTab();

      // Configurar escucha de cambios en el historial
      this.setupEventListeners();

      // Cargar perfil del estudiante
      this.loadStudentProfile();
    },

    setupEventListeners() {
      // setting up event listeners

      // Escuchar cambios en el historial (botones atrás/adelante del navegador)
      window.addEventListener("popstate", () => {
        // popstate detected
        this.handleLocationChange();
      });

      // Escuchar cambios en hash
      window.addEventListener("hashchange", () => {
        // hashchange detected
        this.handleLocationChange();
      });
    },

    // Manejar cambio de ubicación
    handleLocationChange() {
      // handle location change
      const tabFromUrl = this.getTabFromUrl();

      if (tabFromUrl && this.isValidTab(tabFromUrl)) {
        // set active tab from URL
        this.activeTab = tabFromUrl;
        localStorage.setItem("studentActiveTab", tabFromUrl);
      } else {
        // Si no hay hash válido, usar el guardado o por defecto
        const savedTab = localStorage.getItem("studentActiveTab");
        if (savedTab && this.isValidTab(savedTab)) {
          this.activeTab = savedTab;
          // using saved tab
          // Actualizar URL para reflejar el estado
          if (savedTab === "overview") {
            history.replaceState(null, "", window.location.pathname);
          } else {
            window.location.hash = savedTab;
          }
        } else {
          this.activeTab = "overview";
          // using default tab: overview
        }
      }
    },

    // ✨ Corregida función para obtener pestaña de la URL
    getTabFromUrl() {
      const hash = window.location.hash.substring(1); // Remover #
      // get tab from URL hash

      // ✨ Manejar correctamente el hash vacío
      if (hash === "") {
        // Si el hash está vacío, no asumir "overview"
        // Dejar que otras funciones decidan
        return null;
      }

      return this.isValidTab(hash) ? hash : null;
    },

    // Validar si una pestaña es válida
    isValidTab(tabId) {
      const validTabs = [
        "overview",
        "events",
        "event_activities",
        "registrations",
        "profile",
      ];
      const isValid = validTabs.includes(tabId);
      return isValid;
    },

    // Establecer pestaña inicial
    setInitialTab() {
      // setting initial tab (verbose logs removed)

      try {
        // 1. Primero intentar obtener la pestaña de la URL (hash)
        const tabFromUrl = this.getTabFromUrl();
        // tabFromUrl available

        if (tabFromUrl && this.isValidTab(tabFromUrl)) {
          // using tab from URL
          this.activeTab = tabFromUrl;
          localStorage.setItem("studentActiveTab", tabFromUrl);
          return;
        }

        // 2. Si no hay tab en URL, intentar obtener del localStorage
        const savedTab = localStorage.getItem("studentActiveTab");
        // savedTab from localStorage

        if (savedTab && this.isValidTab(savedTab)) {
          // using saved tab
          this.activeTab = savedTab;

          // Actualizar URL para reflejar el estado guardado
          this.updateLocationAndStorage(savedTab);
          return;
        }

        // 3. Si no hay tab guardada, usar la por defecto
        // fallback to default tab: overview
        this.activeTab = "overview";
        localStorage.setItem("studentActiveTab", "overview");

        // Limpiar hash para overview
        if (window.location.hash && window.location.hash !== "#overview") {
          try {
            history.replaceState(null, "", window.location.pathname);
          } catch (e) {
            console.warn("Could not clear hash:", e);
          }
        }
      } catch (error) {
        console.error("❌ Error setting initial tab:", error);
        // Fallback: usar overview por defecto
        this.activeTab = "overview";
        localStorage.setItem("studentActiveTab", "overview");
      }

      // final activeTab set
    },

    // Cambiar pestaña
    setActiveTab(tabId) {
      if (!this.isValidTab(tabId)) {
        console.warn(`Invalid tab ID: ${tabId}`);
        return;
      }

      const previousTab = this.activeTab;
      this.activeTab = tabId;

      // ✨ Refrescar contenido automáticamente cuando se cambia a ciertas pestañas
      this.refreshTabContent(tabId, previousTab);

      // Actualizar URL y localStorage
      this.updateLocationAndStorage(tabId);
    },

    // ✨ Refrescar contenido automáticamente cuando se cambia de pestaña
    async refreshTabContent(currentTab, previousTab) {
      try {
        switch (currentTab) {
          case "registrations":
            // Refrescar preregistros cuando se cambia a la pestaña de preregistros
            await this.refreshRegistrations();
            break;

          case "events":
            // Refrescar eventos cuando se cambia a la pestaña de eventos
            const eventsElement = document.querySelector(
              '[x-data*="studentEventsManager"]'
            );
            if (eventsElement && eventsElement.__x) {
              const eventsManager = eventsElement.__x.getUnobservedData();
              if (typeof eventsManager.loadEvents === "function") {
                await eventsManager.loadEvents(
                  eventsManager.pagination.current_page || 1
                );
              }
            }
            break;

          case "event_activities":
            // Refrescar actividades del evento actual cuando se cambia a la pestaña de actividades
            const activitiesElement = document.querySelector(
              '[x-data*="studentEventActivitiesManager"]'
            );
            if (activitiesElement && activitiesElement.__x) {
              const activitiesManager =
                activitiesElement.__x.getUnobservedData();
              if (
                typeof activitiesManager.refreshCurrentEventActivities ===
                "function"
              ) {
                await activitiesManager.refreshCurrentEventActivities();
              }
            }
            break;

          default:
          // Para otras pestañas, no hacer nada especial
        }
      } catch (error) {
        console.error(
          `❌ Error refrescando contenido para pestaña ${currentTab}:`,
          error
        );
      }
    },

    // Actualizar URL y almacenamiento local
    updateLocationAndStorage(tabId) {
      // update location and storage for tab

      // Guardar en localStorage
      localStorage.setItem("studentActiveTab", tabId);

      // Actualizar URL
      try {
        if (tabId === "overview") {
          // Para la pestaña por defecto, limpiar el hash
          if (window.location.hash && window.location.hash !== "") {
            history.pushState(null, "", window.location.pathname);
          }
        } else {
          const currentHash = window.location.hash.substring(1);
          if (currentHash !== tabId) {
            window.location.hash = tabId;
          }
        }
      } catch (e) {
        console.warn("Could not update URL hash:", e);
      }
    },

    // Cargar perfil del estudiante
    async loadStudentProfile() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        const response = await fetch("/api/auth/profile?type=student", {
          headers: window.getAuthHeaders(),
        });

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(
            `Error al cargar perfil: ${response.status} ${response.statusText}`
          );
        }

        const data = await response.json();

        if (data.student) {
          this.studentName = data.student.full_name || "Estudiante";
          this.studentControlNumber = data.student.control_number || "";
          this.studentCareer = data.student.career || "";
          this.studentEmail = data.student.email || "";

          // Guardar en localStorage para acceso rápido
          localStorage.setItem("studentProfile", JSON.stringify(data.student));
        } else {
          // Si no es estudiante, redirigir al login
          this.redirectToLogin();
        }
      } catch (error) {
        console.error("Error loading student profile:", error);
        this.errorMessage =
          error.message || "Error al cargar perfil del estudiante";
        showToast(this.errorMessage, "error");
      }
    },

    async viewEventDetails(event) {
      this.currentEvent = { ...event };

      // Cargar actividades del evento
      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        // Solicitar actividades visibles para estudiantes
        const response = await fetch(
          `/api/activities?event_id=${event.id}&for_student=true`,
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
            `Error al cargar actividades: ${response.status} ${response.statusText}`
          );
        }

        const data = await response.json();

        // Defensive client-side filter: ensure forbidden activity types are removed
        const filtered = (data.activities || []).filter(
          (a) => String(a.activity_type).toLowerCase() !== "magistral"
        );

        // Mapear actividades y formatear fechas
        this.currentEventActivities = filtered.map((activity) => ({
          ...activity,
          start_datetime: this.formatDateTimeForInput(activity.start_datetime),
          end_datetime: this.formatDateTimeForInput(activity.end_datetime),
        }));

        this.showEventModal = true;
      } catch (error) {
        console.error("Error loading event activities:", error);
        this.errorMessage =
          error.message || "Error al cargar actividades del evento";
        showToast(this.errorMessage, "error");
        this.showEventModal = true; // Mostrar el modal aunque no se carguen las actividades
        this.currentEventActivities = [];
      }
    },

    // ✨ Verificar si es evento de un solo día
    isSingleDayEvent(event) {
      if (!event || !event.start_date || !event.end_date) return false;

      const startDate = new Date(event.start_date);
      const endDate = new Date(event.end_date);

      // Comparar solo la fecha (sin hora)
      return startDate.toDateString() === endDate.toDateString();
    },

    // ✨ Agrupar actividades por día
    groupActivitiesByDay(activities) {
      if (!activities || activities.length === 0) return {};

      const grouped = {};

      activities.forEach((activity) => {
        const startDate = new Date(activity.start_datetime);
        const endDate = new Date(activity.end_datetime);

        // ✨ Para actividades multídias: crear entradas para cada día
        if (this.isMultiDayActivity(startDate, endDate)) {
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
              // ✨ Marcar como actividad expandida
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

      return sortedGrouped;
    },

    // ✨ Verificar si una actividad es multídias
    isMultiDayActivity(startDate, endDate) {
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

    // ✨ Obtener todas las fechas entre dos fechas (inclusive)
    getDatesBetween(startDate, endDate) {
      const dates = [];
      const currentDate = new Date(startDate);
      const finalDate = new Date(endDate);

      currentDate.setHours(0, 0, 0, 0);
      finalDate.setHours(0, 0, 0, 0);

      while (currentDate <= finalDate) {
        dates.push(currentDate.toISOString().split("T")[0]); // YYYY-MM-DD
        currentDate.setDate(currentDate.getDate() + 1);
      }

      return dates;
    },

    // ✨ Obtener el número del día actual dentro de la serie multidia (1/3, 2/3, etc.)
    getDayInSeries(startDate, endDate, currentDateStr) {
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
      const currentDay = new Date(currentDateStr);

      // Calcular el número de días desde el inicio
      const timeDiff = currentDay.getTime() - startDay.getTime();
      const daysFromStart = Math.floor(timeDiff / (1000 * 60 * 60 * 24)) + 1;

      return daysFromStart;
    },

    // ✨ Obtener el total de días de la actividad multidia
    getTotalDays(startDate, endDate) {
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
    },

    // ✨ Obtener actividades ordenadas por hora (para eventos de un solo día)
    getSortedActivitiesByTime(activities) {
      if (!activities || activities.length === 0) return [];

      return [...activities].sort((a, b) => {
        return new Date(a.start_datetime) - new Date(b.start_datetime); // Orden ascendente
      });
    },

    formatOnlyDate(dateTimeString) {
      return window.formatOnlyDate
        ? window.formatOnlyDate(dateTimeString)
        : "Sin fecha";
    },

    // Formatear fecha para input datetime-local
    formatDateTimeForInput(dateTimeString) {
      return window.formatDateTimeForInput
        ? window.formatDateTimeForInput(dateTimeString)
        : "";
    },

    // Formatear fecha para mostrar
    formatDate(dateTimeString) {
      return window.formatDate
        ? window.formatDate(dateTimeString)
        : "Sin fecha";
    },

    // Formatear fecha y hora para mostrar
    formatDateTime(dateTimeString) {
      return window.formatDateTime
        ? window.formatDateTime(dateTimeString)
        : "Sin fecha";
    },

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

    // Logout
    logout() {
      if (confirm("¿Estás seguro de cerrar sesión?")) {
        localStorage.removeItem("authToken");
        localStorage.removeItem("userType");
        localStorage.removeItem("studentProfile");
        window.location.href = "/";
      }
    },

    async refreshRegistrations() {
      try {
        // Intentar encontrar el componente de preregistros y refrescarlo
        const registrationsElement = document.querySelector(
          '[x-data*="studentRegistrationsManager"]'
        );
        if (registrationsElement && registrationsElement.__x) {
          const registrationsManager =
            registrationsElement.__x.getUnobservedData();
          if (typeof registrationsManager.loadRegistrations === "function") {
            // Refrescar en la página actual o primera página
            await registrationsManager.loadRegistrations(
              registrationsManager.pagination.current_page || 1
            );
            return true;
          }
        }
        return false;
      } catch (error) {
        console.error("❌ Error refrescando preregistros:", error);
        return false;
      }
    },

    getPageTitle() {
      const titles = {
        overview: "Resumen",
        events: "Eventos Disponibles",
        event_activities: "Actividades del Evento",
        registrations: "Mis Preregistros",
        profile: "Mi Perfil",
      };
      return titles[this.activeTab] || "Eventos Tec";
    },
  };
}

// Hacer la función globalmente disponible
window.studentDashboard = studentDashboard;
