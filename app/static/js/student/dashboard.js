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
      { id: "history", name: "Histórico de Horas", icon: "ti ti-history" },
      { id: "profile", name: "Mi Perfil", icon: "ti ti-user" },
    ],

    // Inicialización
    init() {
      // initialization (verbose logs removed)

      // Lazy-init de pestañas (Fase D): flag antes de que los parciales
      // (x-init="init()") se inicialicen; ver admin/dashboard.js.
      window.__LAZY_TABS__ = true;

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

      // Lazy-init: despachar la pestaña activa cuando todos los parciales
      // hayan registrado sus listeners (microtask tras la tarea de init)
      const dispatchInitial = () => this.dispatchTabActivated();
      if (typeof queueMicrotask === "function") {
        queueMicrotask(dispatchInitial);
      } else {
        Promise.resolve().then(dispatchInitial);
      }
    },

    // Avisar a la pestaña activa que debe cargar sus datos (lazy-init)
    dispatchTabActivated(tabId) {
      try {
        window.dispatchEvent(
          new CustomEvent("tab:activated", {
            detail: { tab: tabId || this.activeTab },
          }),
        );
      } catch (e) {
        try {
          window.dispatchEvent(new Event("tab:activated"));
        } catch (err) {
          // entorno sin DOM (tests)
        }
      }
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

      console.debug &&
        console.debug(
          "[studentDashboard] handleLocationChange -> tabFromUrl:",
          tabFromUrl,
        );

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

      // Lazy-init: avisar al parcial de la pestaña resultante
      this.dispatchTabActivated();
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
        "history",
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
        console.debug &&
          console.debug(
            "[studentDashboard] setInitialTab -> tabFromUrl:",
            tabFromUrl,
          );

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

      // Lazy-init: avisar al parcial de esta pestaña para que cargue sus
      // datos (si aún no lo hizo)
      this.dispatchTabActivated(tabId);

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
              '[x-data*="studentEventsManager"]',
            );
            if (eventsElement && eventsElement.__x) {
              const eventsManager = eventsElement.__x.getUnobservedData();
              if (typeof eventsManager.loadEvents === "function") {
                await eventsManager.loadEvents(
                  eventsManager.pagination.current_page || 1,
                );
              }
            }
            break;

          case "event_activities":
            // Refrescar actividades del evento actual cuando se cambia a la pestaña de actividades
            const activitiesElement = document.querySelector(
              '[x-data*="studentEventActivitiesManager"]',
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

          case "history":
            // Forzar la carga del histórico cuando el usuario cambia a la pestaña
            // (cubre el caso en que el manager no haya podido cargar en init)
            const historyElement = document.querySelector(
              '[x-data*="studentHistoryManager"]',
            );
            if (historyElement && historyElement.__x) {
              const historyManager = historyElement.__x.getUnobservedData();
              if (typeof historyManager.loadHistory === "function") {
                try {
                  await historyManager.loadHistory();
                } catch (err) {
                  console.error("Error forcing history load:", err);
                }
              }
            }
            break;

          default:
          // Para otras pestañas, no hacer nada especial
        }
      } catch (error) {
        console.error(
          `❌ Error refrescando contenido para pestaña ${currentTab}:`,
          error,
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
        const token = window.getAuthToken
          ? window.getAuthToken()
          : localStorage.getItem("authToken");
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
            `Error al cargar perfil: ${response.status} ${response.statusText}`,
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
        const token = window.getAuthToken
          ? window.getAuthToken()
          : localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        // Solicitar actividades visibles para estudiantes
        const response = await fetch(
          `/api/activities?event_id=${event.id}&for_student=true`,
          {
            headers: window.getAuthHeaders(),
          },
        );

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(
            `Error al cargar actividades: ${response.status} ${response.statusText}`,
          );
        }

        const data = await response.json();

        // Defensive client-side filter: ensure forbidden activity types are removed
        const filtered = (data.activities || []).filter(
          (a) => String(a.activity_type).toLowerCase() !== "magistral",
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

    // Formatear fecha para input datetime-local
    formatDateTimeForInput(dateTimeString) {
      return window.formatDateTimeForInput
        ? window.formatDateTimeForInput(dateTimeString)
        : "";
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
      // Delegar al logout central de app.js, que además revoca el token en
      // el servidor (POST /api/auth/logout). Sin app.js (tests), limpieza local.
      if (
        typeof window !== "undefined" &&
        typeof window.logout === "function"
      ) {
        window.logout();
        return;
      }
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
          '[x-data*="studentRegistrationsManager"]',
        );
        if (registrationsElement && registrationsElement.__x) {
          const registrationsManager =
            registrationsElement.__x.getUnobservedData();
          if (typeof registrationsManager.loadRegistrations === "function") {
            // Refrescar en la página actual o primera página
            await registrationsManager.loadRegistrations(
              registrationsManager.pagination.current_page || 1,
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
        history: "Histórico de Horas",
        profile: "Mi Perfil",
      };
      return titles[this.activeTab] || "Eventos Tec";
    },
  };
}

// Hacer la función globalmente disponible
window.studentDashboard = studentDashboard;
