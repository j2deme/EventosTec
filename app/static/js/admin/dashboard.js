console.log("Admin Dashboard JS loaded");

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
        label: "Total Estudiantes",
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
        label: "Actividades",
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
      { id: "reports", name: "Reportes", icon: "ti ti-chart-bar" },
    ],

    events: [],
    activities: [],
    upcomingEvents: [],
    recentActivities: [],
    recentReports: [],

    // Inicialización
    init() {
      console.log("Initializing admin dashboard component...");

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
        console.log("Popstate event triggered");
        this.handleLocationChange();
      });
    },

    setupDataUpdateListeners() {
      const events = [
        "event-created",
        "event-updated",
        "event-deleted",
        "activity-created",
        "activity-deleted",
      ];
      events.forEach((eventName) => {
        window.addEventListener(eventName, (e) => {
          console.log(`${eventName} detected, reloading stats...`);
          this.loadStats();
          // Recargar datos específicos si es necesario
          if (eventName.includes("event")) this.loadEvents();
          if (eventName.includes("activity")) this.loadActivities();
        });
      });
    },

    handleLocationChange() {
      const tabFromUrl = this.getTabFromUrl();
      if (tabFromUrl && this.isValidTab(tabFromUrl)) {
        console.log(`Setting active tab from URL: ${tabFromUrl}`);
        this.activeTab = tabFromUrl;
      } else {
        // Si no hay hash válido, usar el guardado o por defecto
        const savedTab = localStorage.getItem("adminActiveTab");
        if (savedTab && this.isValidTab(savedTab)) {
          console.log(`Setting active tab from localStorage: ${savedTab}`);
          this.activeTab = savedTab;
          // Actualizar URL para reflejar el estado
          if (savedTab === "overview") {
            history.replaceState(null, "", window.location.pathname);
          } else {
            window.location.hash = savedTab;
          }
        } else {
          console.log("Using default tab: overview");
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
      return ["overview", "events", "activities", "reports"].includes(tabId);
    },

    // Establecer pestaña inicial
    setInitialTab() {
      const tabFromUrl = this.getTabFromUrl();

      if (tabFromUrl && this.isValidTab(tabFromUrl)) {
        console.log(`Initial tab from URL: ${tabFromUrl}`);
        this.activeTab = tabFromUrl;
        return;
      }

      const savedTab = localStorage.getItem("adminActiveTab");
      if (savedTab && this.isValidTab(savedTab)) {
        console.log(`Initial tab from localStorage: ${savedTab}`);
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

      console.log("Using default initial tab: overview");
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

      console.log(`Changing to tab: ${tabId}`);
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
      console.log("Initializing admin dashboard...");
      await this.loadDashboardData();
    },

    async loadDashboardData() {
      this.isLoading = true;
      try {
        await Promise.all([
          this.loadEvents(),
          this.loadActivities(),
          this.loadStats(), // Cargar stats solo una vez
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
        const response = await fetch("/api/events/", {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (response.ok) {
          const data = await response.json();
          this.events = Array.isArray(data) ? data : data.events || [];
          // Actualizar estadísticas
          this.updateStats();
        }
      } catch (error) {
        console.error("Error loading events:", error);
      }
    },

    async loadActivities() {
      try {
        const token = localStorage.getItem("authToken");
        const response = await fetch("/api/activities/", {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (response.ok) {
          const data = await response.json();
          this.activities = Array.isArray(data) ? data : data.activities || [];
          // Actualizar estadísticas
          this.updateStats();
        }
      } catch (error) {
        console.error("Error loading activities:", error);
      }
    },

    async loadStats() {
      // Cargar estadísticas reales desde la API
      try {
        const token = localStorage.getItem("authToken");

        // Ejemplo: cargar estadísticas generales
        const statsResponse = await fetch("/api/stats/", {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (statsResponse.ok) {
          const statsData = await statsResponse.json(); // Esto es un OBJETO, no un arreglo

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
          // Opcional: manejar errores de respuesta no ok
        }
      } catch (error) {
        console.error("Error loading stats:", error);
        // Mantener stats simulados si falla
        // Opcional: mostrar mensaje de error al usuario
      }
    },

    updateStats() {
      // Actualizar valores basados en datos cargados
      this.stats = this.stats.map((stat) => {
        switch (stat.id) {
          case "events":
            return { ...stat, value: this.events.length.toString() };
          case "activities":
            return { ...stat, value: this.activities.length.toString() };
          default:
            return stat;
        }
      });
    },

    // Métodos de navegación
    toggleSidebar() {
      this.sidebarOpen = !this.sidebarOpen;
    },

    // Métodos de utilidad
    formatDate(dateString) {
      if (!dateString) return "Sin fecha";
      try {
        const date = new Date(dateString);
        return date.toLocaleDateString("es-ES", {
          year: "numeric",
          month: "short",
          day: "numeric",
        });
      } catch (e) {
        return dateString;
      }
    },

    formatTime(dateString) {
      if (!dateString) return "--:--";
      try {
        const date = new Date(dateString);
        return date.toLocaleTimeString("es-ES", {
          hour: "2-digit",
          minute: "2-digit",
        });
      } catch (e) {
        return "--:--";
      }
    },

    // Métodos de acción
    openEventModal() {
      alert("Abrir modal para crear/editar evento");
    },

    editEvent(eventId) {
      alert(`Editar evento ${eventId}`);
    },

    deleteEvent(eventId) {
      if (confirm(`¿Estás seguro de eliminar el evento ${eventId}?`)) {
        alert(`Eliminar evento ${eventId}`);
      }
    },

    openActivityModal() {
      alert("Abrir modal para crear/editar actividad");
    },

    editActivity(activityId) {
      alert(`Editar actividad ${activityId}`);
    },

    deleteActivity(activityId) {
      if (confirm(`¿Estás seguro de eliminar la actividad ${activityId}?`)) {
        alert(`Eliminar actividad ${activityId}`);
      }
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

// Hacer la función globalmente disponible
window.adminDashboard = adminDashboard;

if (typeof window.eventsManager === "undefined") {
  window.eventsManager = eventsManager;
}
