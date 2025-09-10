// static/js/student/dashboard.js
console.log("Student Dashboard JS loaded");

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
      console.log("Initializing student dashboard...");
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
        console.log(`Setting active tab from URL: ${tabFromUrl}`);
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

      // Actualizar URL y localStorage
      this.updateLocationAndStorage(tabId);
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
          console.log("Profile ", data); // Para debugging

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
  };
}

// Hacer la función globalmente disponible
window.studentDashboard = studentDashboard;
