// static/js/student/profile.js
console.log("Student Profile Manager JS loaded");

function studentProfileManager() {
  return {
    // Estado
    loading: false,
    errorMessage: "",

    // Datos del estudiante
    studentData: {
      id: null,
      control_number: "",
      full_name: "",
      career: "",
      email: "",
    },

    // Metadata
    lastUpdated: null,

    // Inicialización
    init() {
      console.log("Initializing student profile manager...");
      this.loadProfile();
    },

    // Cargar perfil del estudiante
    async loadProfile() {
      this.loading = true;
      this.errorMessage = "";

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
            this.studentData = {
              id: data.student.id || null,
              control_number: data.student.control_number || "",
              full_name: data.student.full_name || "",
              career: data.student.career || "",
              email: data.student.email || "",
            };

            // Guardar fecha de última actualización
            this.lastUpdated = new Date();

            // Guardar en localStorage para acceso rápido
            localStorage.setItem(
              "studentProfile",
              JSON.stringify(this.studentData)
            );
          } else {
            this.errorMessage = "No se encontraron datos del estudiante";
            showToast(this.errorMessage, "error");
          }
        } else {
          if (response.status === 401) {
            this.redirectToLogin();
          } else {
            const errorData = await response.json();
            this.errorMessage =
              errorData.message || "Error al cargar el perfil";
            showToast(this.errorMessage, "error");
          }
        }
      } catch (error) {
        console.error("Error loading student profile:", error);
        this.errorMessage = "Error de conexión al cargar el perfil";
        showToast(this.errorMessage, "error");
      } finally {
        this.loading = false;
      }
    },

    // Formatear fecha y hora
    formatDateTime(dateTimeString) {
      if (!dateTimeString) return "No disponible";

      try {
        const date = new Date(dateTimeString);
        return date.toLocaleString("es-ES", {
          year: "numeric",
          month: "long",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        });
      } catch (e) {
        return dateTimeString;
      }
    },

    // Cerrar sesión
    logout() {
      if (confirm("¿Estás seguro de cerrar sesión?")) {
        localStorage.removeItem("authToken");
        localStorage.removeItem("userType");
        localStorage.removeItem("studentProfile");
        window.location.href = "/";
      }
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
window.studentProfileManager = studentProfileManager;
