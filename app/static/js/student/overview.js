// static/js/student/overview.js
console.log("Student Overview Manager JS loaded");

function studentOverviewManager() {
  return {
    // Datos del estudiante
    studentName: "",
    studentControlNumber: "",

    // Estado
    stats: [
      {
        id: "total_registrations",
        label: "Preregistros",
        value: "0",
        icon: "ti ti-bookmark",
        color: "#4f46e5",
        bgColor: "bg-indigo-100",
      },
      {
        id: "confirmed_registrations",
        label: "Confirmados",
        value: "0",
        icon: "ti ti-check",
        color: "#10b981",
        bgColor: "bg-green-100",
      },
      {
        id: "attended_activities",
        label: "Asistencias",
        value: "0",
        icon: "ti ti-user-check",
        color: "#f59e0b",
        bgColor: "bg-yellow-100",
      },
      {
        id: "upcoming_events",
        label: "Eventos Activos",
        value: "0",
        icon: "ti ti-calendar-event",
        color: "#ef4444",
        bgColor: "bg-red-100",
      },
    ],

    // Datos de eventos y preregistros
    upcomingEvents: [],
    recentRegistrations: [],
    loadingUpcoming: false,
    loadingRegistrations: false,

    // Inicialización
    init() {
      console.log("Initializing student overview manager...");
      this.loadStudentProfile();
      this.loadStats();
      this.loadUpcomingEvents();
      this.loadRecentRegistrations();
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
          }
        } else if (response.status === 401) {
          this.redirectToLogin();
        }
      } catch (error) {
        console.error("Error loading student profile:", error);
      }
    },

    // Cargar estadísticas
    async loadStats() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        // Obtener el ID del estudiante
        const studentId = this.getCurrentStudentId();
        if (!studentId) return;

        // Cargar estadísticas de preregistros
        const registrationsResponse = await fetch(
          `/api/registrations?student_id=${studentId}`,
          {
            headers: window.getAuthHeaders(),
          }
        );

        if (registrationsResponse.ok) {
          const registrationsData = await registrationsResponse.json();
          const registrations = registrationsData.registrations || [];

          // Calcular estadísticas
          const totalRegistrations = registrations.length;
          const confirmedRegistrations = registrations.filter(
            (r) => r.status === "Confirmado" || r.status === "Asistió"
          ).length;
          const attendedActivities = registrations.filter(
            (r) => r.status === "Asistió"
          ).length;

          // Actualizar stats
          this.stats = this.stats.map((stat) => {
            switch (stat.id) {
              case "total_registrations":
                return { ...stat, value: totalRegistrations.toString() };
              case "confirmed_registrations":
                return { ...stat, value: confirmedRegistrations.toString() };
              case "attended_activities":
                return { ...stat, value: attendedActivities.toString() };
              default:
                return stat;
            }
          });
        }

        // Cargar estadísticas de eventos activos
        const eventsResponse = await fetch("/api/events?status=active", {
          headers: window.getAuthHeaders(),
        });

        if (eventsResponse.ok) {
          const eventsData = await eventsResponse.json();
          const activeEvents = eventsData.events ? eventsData.events.length : 0;

          this.stats = this.stats.map((stat) => {
            if (stat.id === "upcoming_events") {
              return { ...stat, value: activeEvents.toString() };
            }
            return stat;
          });
        }
      } catch (error) {
        console.error("Error loading stats:", error);
      }
    },

    // Cargar eventos próximos
    async loadUpcomingEvents() {
      this.loadingUpcoming = true;
      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        // Obtener eventos activos que aún no han terminado
        const now = new Date().toISOString();
        const response = await fetch(
          `/api/events?status=active&sort=start_date:asc`,
          {
            headers: window.getAuthHeaders(),
          }
        );

        if (response.ok) {
          const data = await response.json();
          const events = data.events || [];

          // Filtrar eventos futuros
          this.upcomingEvents = events.filter((event) => {
            const eventEndDate = new Date(event.end_date);
            return eventEndDate >= new Date();
          });
        }
      } catch (error) {
        console.error("Error loading upcoming events:", error);
      } finally {
        this.loadingUpcoming = false;
      }
    },

    // Cargar preregistros recientes
    async loadRecentRegistrations() {
      this.loadingRegistrations = true;
      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          this.redirectToLogin();
          return;
        }

        // Obtener el ID del estudiante
        const studentId = this.getCurrentStudentId();
        if (!studentId) return;

        // Cargar preregistros recientes del estudiante
        const response = await fetch(
          `/api/registrations?student_id=${studentId}&sort=registration_date:desc&per_page=5`,
          {
            headers: window.getAuthHeaders(),
          }
        );

        if (response.ok) {
          const data = await response.json();
          this.recentRegistrations = data.registrations || [];
        }
      } catch (error) {
        console.error("Error loading recent registrations:", error);
      } finally {
        this.loadingRegistrations = false;
      }
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

    // Navegar a la vista de preregistros
    goToRegistrations() {
      console.log("Intentando navegar a preregistros...");

      try {
        // Método más robusto para encontrar y cambiar la pestaña
        let dashboard = null;

        // Intentar encontrar el dashboard de varias maneras
        const possibleSelectors = [
          '[x-data*="studentDashboard"]',
          '[x-data^="studentDashboard"]',
          "[x-data]",
        ];

        // Buscar el elemento Alpine del dashboard
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
          console.log(
            "Dashboard encontrado, cambiando a pestaña 'registrations'"
          );
          dashboard.__x.getUnobservedData().setActiveTab("registrations");
        } else {
          // Si no encontramos el dashboard de la manera tradicional,
          // intentar una navegación directa mediante el hash
          console.log("Dashboard no encontrado, intentando navegación directa");
          window.location.hash = "registrations";

          // También intentar disparar un evento personalizado por si acaso
          window.dispatchEvent(
            new CustomEvent("navigate-to-tab", {
              detail: { tab: "registrations" },
            })
          );
        }
      } catch (error) {
        console.error("Error al navegar a preregistros:", error);

        // Como último recurso, intentar navegación directa
        try {
          window.location.hash = "registrations";
        } catch (fallbackError) {
          console.error("Error en navegación de fallback:", fallbackError);
          showToast("Error al navegar a preregistros", "error");
        }
      }
    },

    // Formatear fecha para mostrar
    formatDate(dateTimeString) {
      if (!dateTimeString) return "Sin fecha";
      const date = new Date(dateTimeString);
      return date.toLocaleDateString("es-ES", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
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
window.studentOverviewManager = studentOverviewManager;
