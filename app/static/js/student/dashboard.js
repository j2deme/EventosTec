// static/js/student/dashboard.js
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
      this.setInitialTab();
      this.setupEventListeners();
      this.loadStudentProfile();
    },

    setupEventListeners() {
      // Escuchar cambios en el historial (botones atrás/adelante del navegador)
      window.addEventListener("popstate", () => {
        this.handleLocationChange();
      });

      // Escuchar cambios en hash
      window.addEventListener("hashchange", () => {
        this.handleLocationChange();
      });
    },

    handleLocationChange() {
      const tabFromUrl = this.getTabFromUrl();
      if (tabFromUrl && this.isValidTab(tabFromUrl)) {
        this.activeTab = tabFromUrl;
      } else {
        // Si no hay hash válido, usar el guardado o por defecto
        const savedTab = localStorage.getItem("studentActiveTab");
        if (savedTab && this.isValidTab(savedTab)) {
          this.activeTab = savedTab;
          // Actualizar URL para reflejar el estado
          if (savedTab === "overview") {
            history.replaceState(null, "", window.location.pathname);
          } else {
            window.location.hash = savedTab;
          }
        } else {
          this.activeTab = "overview";
        }
      }
    },

    // Obtener pestaña de la URL
    getTabFromUrl() {
      const hash = window.location.hash.substring(1); // Remover #
      return this.isValidTab(hash) ? hash : null;
    },

    // Validar si una pestaña es válida
    isValidTab(tabId) {
      return [
        "overview",
        "events",
        "registrations",
        "profile",
        "event_activities",
      ].includes(tabId);
    },

    // Establecer pestaña inicial
    setInitialTab() {
      const tabFromUrl = this.getTabFromUrl();

      if (tabFromUrl && this.isValidTab(tabFromUrl)) {
        this.activeTab = tabFromUrl;
        return;
      }

      const savedTab = localStorage.getItem("studentActiveTab");
      if (savedTab && this.isValidTab(savedTab)) {
        this.activeTab = savedTab;

        // Actualizar URL para reflejar el estado guardado
        if (savedTab === "overview") {
          // Para overview, limpiar el hash si existe
          if (window.location.hash) {
            history.replaceState(null, "", window.location.pathname);
          }
        } else {
          // Para otras pestañas, asegurar que el hash esté presente
          if (window.location.hash !== `#${savedTab}`) {
            window.location.hash = savedTab;
          }
        }
        return;
      }

      this.activeTab = "overview";
      // Asegurar que el hash se limpie para overview
      if (window.location.hash) {
        history.replaceState(null, "", window.location.pathname);
      }
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
      // Guardar en localStorage
      localStorage.setItem("studentActiveTab", tabId);

      // Actualizar URL
      try {
        if (tabId === "overview") {
          // Para la pestaña por defecto, limpiar el hash
          if (window.location.hash) {
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

        if (response.ok) {
          const data = await response.json();

          if (data.student) {
            this.studentName = data.student.full_name || "Estudiante";
            this.studentControlNumber = data.student.control_number || "";
            this.studentCareer = data.student.career || "";
            this.studentEmail = data.student.email || "";

            // Guardar en localStorage para acceso rápido
            localStorage.setItem(
              "studentProfile",
              JSON.stringify(data.student)
            );
          } else {
            // Si no es estudiante, redirigir al login
            this.redirectToLogin();
          }
        } else {
          // Si hay error de autenticación, redirigir al login
          if (response.status === 401) {
            this.redirectToLogin();
          } else {
            showToast("Error al cargar el perfil del estudiante", "error");
          }
        }
      } catch (error) {
        console.error("Error loading student profile:", error);
        showToast("Error de conexión al cargar el perfil", "error");
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

        const response = await fetch(`/api/activities?event_id=${event.id}`, {
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
        this.currentEventActivities = data.activities.map((activity) => ({
          ...activity,
          start_datetime: this.formatDateTimeForInput(activity.start_datetime),
          end_datetime: this.formatDateTimeForInput(activity.end_datetime),
        }));

        this.showEventModal = true;
      } catch (error) {
        console.error("Error loading event activities:", error);
        showToast("Error al cargar actividades del evento", "error");
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
        const dateKey = activity.start_datetime.split("T")[0]; // YYYY-MM-DD
        if (!grouped[dateKey]) {
          grouped[dateKey] = {};
        }

        const activityType = activity.activity_type || "Otro";
        if (!grouped[dateKey][activityType]) {
          grouped[dateKey][activityType] = [];
        }

        grouped[dateKey][activityType].push(activity);
      });

      // Ordenar actividades dentro de cada grupo por hora de inicio
      Object.keys(grouped).forEach((date) => {
        Object.keys(grouped[date]).forEach((type) => {
          grouped[date][type].sort((a, b) => {
            return new Date(a.start_datetime) - new Date(b.start_datetime);
          });
        });
      });

      return grouped;
    },

    // ✨ Obtener actividades ordenadas por hora (para eventos de un solo día)
    getSortedActivitiesByTime(activities) {
      if (!activities || activities.length === 0) return [];

      return [...activities].sort((a, b) => {
        return new Date(a.start_datetime) - new Date(b.start_datetime);
      });
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
    formatDateTimeForInput(dateTimeString) {
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

    // Obtener título de la página
    getPageTitle() {
      const titles = {
        overview: "Resumen",
        events: "Eventos Disponibles",
        registrations: "Mis Preregistros",
        profile: "Mi Perfil",
      };
      return titles[this.activeTab] || "Eventos Tec";
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
  };
}

// Hacer la función globalmente disponible
window.studentDashboard = studentDashboard;
