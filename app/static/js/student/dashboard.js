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
      { id: "registrations", name: "Mis Preregistros", icon: "ti ti-bookmark" },
      { id: "profile", name: "Mi Perfil", icon: "ti ti-user" },
    ],

    // Inicialización
    init() {
      console.log("Initializing student dashboard...");
      if (!this.checkAuthAndLoadProfile()) {
        return;
      }
      this.setInitialTab();
      this.setupEventListeners();
    },

    async checkAuthAndLoadProfile() {
      const token = localStorage.getItem("authToken");
      const userType = localStorage.getItem("userType");

      // Verificación básica
      if (!token || userType !== "student") {
        console.log("No autenticado como estudiante, redirigiendo al login");
        showToast("Por favor inicia sesión como estudiante", "error");
        this.redirectToLogin();
        return false;
      }

      try {
        // Verificar el token contra el endpoint protegido
        const response = await fetch("/api/auth/profile?type=student", {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          console.log("Token inválido, redirigiendo al login");
          this.redirectToLogin();
          return false;
        }

        const data = await response.json();

        // Verificar que sea realmente un estudiante
        if (!data.student) {
          console.log("El perfil no es de estudiante, redirigiendo al login");
          showToast("Acceso denegado", "error");
          this.redirectToLogin();
          return false;
        }

        // Cargar los datos del perfil
        this.loadStudentProfile();
        // console.log("Autenticación verificada exitosamente");
        return true;
      } catch (error) {
        console.error("Error verificando autenticación:", error);
        this.redirectToLogin();
        return false;
      }
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
      return ["overview", "events", "registrations", "profile"].includes(tabId);
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
        if (tabFromUrl === "overview") {
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

    async loadStudentProfile() {
      try {
        const token = localStorage.getItem("authToken");

        if (!token) {
          console.log("❌ No hay token, redirigiendo al login");
          this.redirectToLogin();
          return;
        }

        const response = await fetch("/api/auth/profile?type=student", {
          headers: window.getAuthHeaders(),
        });

        if (response.ok) {
          const data = await response.json();
          //console.log("Datos de perfil completos:", data);

          if (data.student) {
            this.studentName = data.student.full_name || "Estudiante";
            this.studentControlNumber = data.student.control_number || "";
            this.studentCareer = data.student.career || "";
            this.studentEmail = data.student.email || "";
            // Guardar en localStorage para uso rápido
            localStorage.setItem(
              "studentProfile",
              JSON.stringify(data.student)
            );
          } else if (data.user) {
            //console.log(
            //  "❌ Datos de ADMINISTRADOR encontrados - discrepancia de tipo"
            //);
            showToast(
              "Acceso denegado: Se requiere cuenta de estudiante",
              "error"
            );
            this.redirectToLogin();
          } else {
            // console.log("❌ Tipo de perfil desconocido");
            showToast("Datos de perfil inválidos", "error");
            this.redirectToLogin();
          }
        } else {
          console.error("❌ Error en respuesta, status:", response.status);
          if (response.status === 401) {
            console.error("🔒 Error 401, redirigiendo al login");
            this.redirectToLogin();
          }
        }
      } catch (error) {
        console.error("💥 Error loading student profile:", error);
        showToast("Error al cargar el perfil del estudiante", "error");
        // No redirigir inmediatamente por error de red, permitir reintentar
      }
    },

    // Redirigir al login
    redirectToLogin() {
      localStorage.removeItem("authToken");
      localStorage.removeItem("userType");
      window.location.href = "/";
    },

    // Logout
    logout() {
      if (confirm("¿Estás seguro de cerrar sesión?")) {
        localStorage.removeItem("authToken");
        localStorage.removeItem("userType");
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

// Componente para el contenido principal
function studentDashboardContent() {
  return {
    activeTab: "overview",

    init() {
      // Sincronizar con el estado del dashboard principal
      const dashboard = document.querySelector('[x-data*="studentDashboard"]');
      if (dashboard && dashboard.__x) {
        this.activeTab = dashboard.__x.getUnobservedData().activeTab;
      }

      // Escuchar cambios en la pestaña activa
      window.addEventListener("hashchange", () => {
        const dashboard = document.querySelector(
          '[x-data*="studentDashboard"]'
        );
        if (dashboard && dashboard.__x) {
          this.activeTab = dashboard.__x.getUnobservedData().activeTab;
        }
      });
    },

    getPageTitle() {
      const titles = {
        overview: "Resumen",
        events: "Eventos Disponibles",
        registrations: "Mis Preregistros",
        profile: "Mi Perfil",
      };
      const dashboard = document.querySelector('[x-data*="studentDashboard"]');
      if (dashboard && dashboard.__x) {
        const activeTab = dashboard.__x.getUnobservedData().activeTab;
        return titles[activeTab] || "Eventos Tec";
      }
      return "Eventos Tec";
    },
  };
}

window.studentDashboardContent = studentDashboardContent;
