// attendances.js - clean Alpine component for admin quick-register
// Exports window.attendancesAdmin

function attendancesAdmin() {
  return {
    activities: [],
    query: "",
    activityId: "",
    resultsHtml: "",
    showModal: false,
    modalStudentId: "",
    modalActivityId: "",
    modalMarkPresent: true,

    init() {
      this.loadActivities();
      // Registrar listeners globales una sola vez
      try {
        window.addEventListener("open-assign-modal", () => {
          const c = document.getElementById("attendances-assign-container");
          if (c) c.style.display = "";
        });
        window.addEventListener("open-list-tab", () => {
          const c = document.getElementById("attendances-list-container");
          if (c) c.style.display = "";
        });
      } catch (e) {
        // en entornos de test sin DOM esto puede fallar silenciosamente
      }
    },

    async loadActivities() {
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f("/api/activities");
        if (!res.ok) throw new Error("No se pudieron cargar actividades");
        const data = await res.json();
        this.activities = data.activities || [];
      } catch (err) {
        console.error(err);
        if (typeof showToast === "function")
          showToast("Error al cargar actividades", "error");
      }
    },

    async search() {
      const q = this.query.trim();
      if (!q)
        return (this.resultsHtml =
          '<div class="text-gray-600">Ingresa un término de búsqueda</div>');
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f(
          "/api/students?search=" + encodeURIComponent(q) + "&per_page=10"
        );
        if (!res.ok) throw new Error("Error en búsqueda");
        const data = await res.json();
        this.renderStudents(data.students || []);
      } catch (err) {
        console.error(err);
        this.resultsHtml =
          '<div class="text-red-600">Error al buscar estudiantes</div>';
        if (typeof showToast === "function")
          showToast("Error al buscar estudiantes", "error");
      }
    },

    renderStudents(students) {
      if (!students || !students.length)
        return (this.resultsHtml =
          '<div class="text-gray-600">No se encontraron estudiantes</div>');
      const rows = students
        .map((s) => {
          const name = s.full_name || "";
          const cn = s.control_number || "";
          const id = s.id || "";
          return `
            <div class="p-2 border rounded mb-2 flex justify-between items-center">
              <div>
                <div class="font-medium">${name} — ${cn}</div>
                <div class="text-sm text-gray-500">ID: ${id}</div>
              </div>
              <div>
                <button class="px-3 py-1 bg-indigo-600 text-white rounded quick-register" data-student-id="${id}">Registrar</button>
              </div>
            </div>`;
        })
        .join("");
      this.resultsHtml = rows;
    },

    openQuickRegister(studentId) {
      if (!this.activityId) {
        if (typeof showToast === "function")
          showToast("Selecciona una actividad primero", "warning");
        return;
      }
      this.modalStudentId = String(studentId);
      this.modalActivityId = String(this.activityId);
      this.modalMarkPresent = true;
      this.showModal = true;
    },

    openRegister() {
      // Abrir modal usando la actividad seleccionada (si hay)
      if (!this.activityId) {
        if (typeof showToast === "function")
          showToast("Selecciona una actividad primero", "warning");
        return;
      }
      this.modalStudentId = "";
      this.modalActivityId = String(this.activityId);
      this.modalMarkPresent = true;
      this.showModal = true;
    },

    async submitModal() {
      const sid = Number(this.modalStudentId);
      const aid = Number(this.modalActivityId);
      const markPresent = !!this.modalMarkPresent;

      if (!sid || !aid) {
        if (typeof showToast === "function")
          showToast("Estudiante y actividad son requeridos", "warning");
        return;
      }

      try {
        const res = await fetch("/api/attendances/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            student_id: sid,
            activity_id: aid,
            mark_present: markPresent,
          }),
        });
        const body = await res.json().catch(function () {
          return {};
        });
        if (res.ok) {
          if (typeof showToast === "function")
            showToast(body.message || "Asistencia registrada", "success");
          this.showModal = false;
        } else {
          if (typeof showToast === "function")
            showToast(body.message || "Error al registrar", "error");
        }
      } catch (err) {
        console.error(err);
        if (typeof showToast === "function")
          showToast("Error al registrar asistencia", "error");
      }
    },

    closeModal() {
      // Cierra el modal y limpia los campos del modal
      this.showModal = false;
      this.modalStudentId = "";
      this.modalActivityId = "";
      this.modalMarkPresent = true;
    },
  };
}

// Delegación global para botones dinámicos (protegida en entornos sin DOM)
try {
  document.addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest(".quick-register") : null;
    if (!btn) return;
    var sid = btn.dataset.studentId;
    var alpineRoot = document.querySelector("[x-data]");
    if (
      alpineRoot &&
      alpineRoot.__x &&
      alpineRoot.__x.$data &&
      typeof alpineRoot.__x.$data.openQuickRegister === "function"
    ) {
      alpineRoot.__x.$data.openQuickRegister(Number(sid));
    }
  });
} catch (e) {
  // En entornos sin DOM (ej. Node/Jest) evitamos fallos al importar el módulo
}

// Exportar la fábrica para Alpine (navegador)
if (typeof window !== "undefined") {
  window.attendancesAdmin = attendancesAdmin;
}

// Exportar para Node/Jest si se requiere (CommonJS)
if (typeof module !== "undefined" && module.exports) {
  module.exports = attendancesAdmin;
}
