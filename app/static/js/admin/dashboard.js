// Función global para el dashboard
function adminDashboard() {
  return {
    // Estado del componente
    sidebarOpen: false,
    activeTab: "overview",
    isLoading: false,
    errorMessage: "",

    // Datos iniciales
    stats: [
      {
        id: "students",
        label: "Estudiantes Registrados",
        value: "0",
        icon: "ti ti-users",
        color: "#4f46e5",
        bgColor: "bg-indigo-100",
      },
      {
        id: "events",
        label: "Eventos Activos",
        value: "0",
        icon: "ti ti-calendar-event",
        color: "#10b981",
        bgColor: "bg-green-100",
      },
      {
        id: "activities",
        label: "Actividades Disponibles",
        value: "0",
        icon: "ti ti-book",
        color: "#f59e0b",
        bgColor: "bg-yellow-100",
      },
      {
        id: "attendances",
        label: "Asistencias Hoy",
        value: "0",
        icon: "ti ti-check",
        color: "#ef4444",
        bgColor: "bg-red-100",
      },
    ],

    menuItems: [
      { id: "overview", name: "Resumen", icon: "ti ti-layout-dashboard" },
      { id: "events", name: "Eventos", icon: "ti ti-calendar-event" },
      { id: "activities", name: "Actividades", icon: "ti ti-book" },
      { id: "registrations", name: "Registros", icon: "ti ti-clipboard-list" },
      { id: "attendances", name: "Asistencias", icon: "ti ti-check" },
      { id: "reports", name: "Reportes", icon: "ti ti-chart-bar" },
    ],

    events: [],
    activities: [],
    upcomingEvents: [],
    recentActivities: [],
    recentReports: [],

    // Inicialización
    init() {
      // 1. Establecer la pestaña inicial PRIMERO
      this.setInitialTab();

      // 2. Configurar escucha de cambios en el historial
      this.setupEventListeners();

      // 3. Cargar datos iniciales
      this.initDashboard();

      // 4. Escuchar eventos personalizados para actualizar datos
      this.setupDataUpdateListeners();
    },

    setupEventListeners() {
      // Escuchar cambios en el historial (botones atrás/adelante del navegador)
      window.addEventListener("popstate", (event) => {
        this.handleLocationChange();
      });

      // Escuchar cambios en hash (cuando se hace clic en enlaces con hash)
      window.addEventListener("hashchange", (event) => {
        this.handleLocationChange();
      });
    },

    setupDataUpdateListeners() {
      window.addEventListener("event-created", () => this.loadEvents());
      window.addEventListener("event-updated", () => this.loadEvents());
      window.addEventListener("event-deleted", () => this.loadEvents());
      window.addEventListener("activity-created", () => this.loadActivities());
      window.addEventListener("activity-updated", () => this.loadActivities());
      window.addEventListener("activity-deleted", () => this.loadActivities());
    },

    handleLocationChange() {
      const tabFromUrl = this.getTabFromUrl();
      if (tabFromUrl && this.isValidTab(tabFromUrl)) {
        this.activeTab = tabFromUrl;
      } else {
        // Si no hay hash válido, usar el guardado o por defecto
        const savedTab = localStorage.getItem("adminActiveTab");
        if (savedTab && this.isValidTab(savedTab)) {
          this.activeTab = savedTab;
          // Actualizar URL para reflejar el estado
          if (savedTab === "overview") {
            history.replaceState(null, "", window.location.pathname);
          } else {
            // Solo actualizar hash si es diferente
            if (window.location.hash !== `#${savedTab}`) {
              window.location.hash = savedTab;
            }
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
        "activities",
        "registrations",
        "reports",
        "attendances",
      ].includes(tabId);
    },

    // Establecer pestaña inicial
    setInitialTab() {
      const tabFromUrl = this.getTabFromUrl();

      if (tabFromUrl && this.isValidTab(tabFromUrl)) {
        this.activeTab = tabFromUrl;
        return;
      }

      const savedTab = localStorage.getItem("adminActiveTab");
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

      // Actualizar URL y localStorage
      this.updateLocationAndStorage(tabId);
    },

    // Actualizar URL y almacenamiento local
    updateLocationAndStorage(tabId) {
      // Guardar en localStorage
      localStorage.setItem("adminActiveTab", tabId);

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

    // Métodos de inicialización
    async initDashboard() {
      await this.loadDashboardData();
    },

    async loadDashboardData() {
      this.isLoading = true;
      try {
        await Promise.all([
          this.loadEvents(),
          this.loadActivities(),
          this.loadStats(),
          this.loadUpcomingEvents(),
          this.loadRecentActivities(),
        ]);
      } catch (error) {
        console.error("Error loading dashboard ", error);
        this.errorMessage = "Error al cargar datos del dashboard";
      } finally {
        this.isLoading = false;
      }
    },

    // Métodos de carga de datos
    async loadEvents() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) return;
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/events/");
        if (response && response.ok) {
          const data = await response.json();
          this.events = Array.isArray(data) ? data : data.events || [];
          this.updateStats();
        }
      } catch (error) {
        console.error("Error loading events:", error);
      }
    },

    async loadActivities() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) return;
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/activities/");
        if (response && response.ok) {
          const data = await response.json();
          this.activities = Array.isArray(data) ? data : data.activities || [];
          this.updateStats();
        }
      } catch (error) {
        console.error("Error loading activities:", error);
        showToast("Error al cargar actividades", "error");
      }
    },

    async loadStats() {
      // Cargar estadísticas reales desde la API
      try {
        const token = localStorage.getItem("authToken");
        if (!token) return;

        // Ejemplo: cargar estadísticas generales
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const statsResponse = await f("/api/stats/");
        if (statsResponse && statsResponse.ok) {
          const statsData = await statsResponse.json();

          // Mapear las propiedades del objeto statsData a las etiquetas de this.stats
          this.stats = this.stats.map((stat) => {
            let value = 0;
            // Asignar el valor correspondiente según la etiqueta del stat existente
            switch (stat.id) {
              case "students":
                value = statsData.total_students || 0;
                break;
              case "events":
                value = statsData.active_events || 0;
                break;
              case "activities":
                value = statsData.total_activities || 0;
                break;
              case "attendances":
                value = statsData.today_attendances || 0;
                break;
              default:
                value = 0; // Valor por defecto si no se encuentra
            }
            // Devolver el stat actualizado con el nuevo valor
            return { ...stat, value: value.toString() }; // Asegurarse de que value sea string
          });
        } else {
          console.error("Error fetching stats, status:", statsResponse.status);
        }
      } catch (error) {
        console.error("Error loading stats:", error);
        // Mantener stats simulados si falla
      }
    },

    async loadUpcomingEvents() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) return;

        // Obtener eventos futuros (próximos 30 días)
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/events?sort=start_date:asc");
        if (response && response.ok) {
          const data = await response.json();
          const events = Array.isArray(data) ? data : data.events || [];

          // Filtrar eventos futuros y añadir campos formateados para las vistas
          const now = new Date();
          const next30Days = new Date();
          next30Days.setDate(now.getDate() + 30);

          const filtered = events
            .filter((event) => {
              const eventStart = new Date(event.start_date);
              return eventStart >= now && eventStart <= next30Days;
            })
            .slice(0, 5); // Limitar a 5 eventos

          // Añadir campos formateados para evitar que las plantillas muestren ISO crudo
          const dh =
            (typeof window !== "undefined" && window.dateHelpers) ||
            (function () {
              try {
                return require("../helpers/dateHelpers");
              } catch (e) {
                return null;
              }
            })();

          this.upcomingEvents = filtered.map((ev) => {
            const startIso = ev.start_date || ev.start || null;
            const createdIso = ev.created_at || ev.created || null;
            return {
              ...ev,
              start_date_formatted:
                (dh && dh.formatDateTime && dh.formatDateTime(startIso)) ||
                (startIso ? String(startIso) : "Sin fecha"),
              start_date_for_input:
                (dh &&
                  dh.formatDateTimeForInput &&
                  dh.formatDateTimeForInput(startIso)) ||
                (startIso ? String(startIso).slice(0, 16) : ""),
              start_time_formatted:
                (dh && dh.formatTime && dh.formatTime(startIso)) ||
                (startIso ? new Date(startIso).toLocaleTimeString() : ""),
              created_at_formatted:
                (dh && dh.formatDateTime && dh.formatDateTime(createdIso)) ||
                (createdIso ? String(createdIso) : ""),
            };
          });
        }
      } catch (error) {
        console.error("Error loading upcoming events:", error);
      }
    },

    async loadRecentActivities() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) return;

        // Obtener actividades recientes (últimos 7 días)
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(
          "/api/activities?sort=created_at:desc&per_page=10"
        );
        if (response && response.ok) {
          const data = await response.json();
          const activities = Array.isArray(data) ? data : data.activities || [];

          // Filtrar actividades recientes
          const now = new Date();
          const last7Days = new Date();
          last7Days.setDate(now.getDate() - 7);

          const recent = activities
            .filter((activity) => {
              const activityCreated = new Date(activity.created_at);
              return activityCreated >= last7Days;
            })
            .slice(0, 5); // Limitar a 5 actividades

          const dh =
            (typeof window !== "undefined" && window.dateHelpers) ||
            (function () {
              try {
                return require("../helpers/dateHelpers");
              } catch (e) {
                return null;
              }
            })();

          this.recentActivities = recent.map((a) => {
            const createdIso = a.created_at || a.created || null;
            return {
              ...a,
              created_at_formatted:
                (dh && dh.formatDateTime && dh.formatDateTime(createdIso)) ||
                (createdIso ? String(createdIso) : "Sin fecha"),
              created_time_formatted:
                (dh && dh.formatTime && dh.formatTime(createdIso)) ||
                (createdIso ? new Date(createdIso).toLocaleTimeString() : ""),
            };
          });
        }
      } catch (error) {
        console.error("Error loading recent activities:", error);
      }
    },

    updateStats() {
      this.loadStats();
    },

    // Métodos de navegación
    toggleSidebar() {
      this.sidebarOpen = !this.sidebarOpen;
    },

    // Métodos de utilidad: delegar formateo a helpers globales
    formatDate(dateString) {
      // Preferir dateHelpers canonical (evitar ambigüedad con globals)
      // Compatibilidad: si existe override dinámico en window, usarlo (tests lo esperan)
      if (
        typeof window !== "undefined" &&
        typeof window.formatDate === "function"
      ) {
        return window.formatDate(dateString);
      }

      try {
        const dh =
          (typeof window !== "undefined" && window.dateHelpers) ||
          require("../helpers/dateHelpers");
        if (dh && typeof dh.formatDate === "function")
          return dh.formatDate(dateString);
      } catch (e) {
        // fallthrough
      }

      return "Sin fecha";
    },

    formatTime(dateString) {
      // Compatibilidad: si existe override dinámico en window, usarlo (tests lo esperan)
      if (
        typeof window !== "undefined" &&
        typeof window.formatTime === "function"
      ) {
        return window.formatTime(dateString);
      }

      try {
        const dh =
          (typeof window !== "undefined" && window.dateHelpers) ||
          require("../helpers/dateHelpers");
        if (dh && typeof dh.formatTime === "function")
          return dh.formatTime(dateString);
      } catch (e) {
        // fallthrough
      }

      if (!dateString) return "--:--";
      const dt = new Date(dateString);
      return dt.toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
      });
    },

    logout() {
      if (confirm("¿Estás seguro de cerrar sesión?")) {
        localStorage.removeItem("authToken");
        localStorage.removeItem("userType");
        window.location.href = "/";
      }
    },
  };
}

// Hacer la función globalmente disponible en navegador
try {
  if (typeof window !== "undefined") {
    window.adminDashboard = adminDashboard;
  }
} catch (e) {
  // no-op in non-browser env
}

// Exportar para Node/Jest (CommonJS)
if (typeof module !== "undefined" && module.exports) {
  module.exports = adminDashboard;
}
