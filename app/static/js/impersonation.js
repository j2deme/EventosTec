// static/js/impersonation.js
// Impersonación de estudiante (Fase B2).
//
// Flujo: el admin llama a POST /api/admin/impersonate y abre
// /dashboard/student#impersonate=<token> en una pestaña nueva. Aquí se ingiere
// el hash (el fragmento NUNCA viaja al servidor) y se guarda en
// sessionStorage — exclusivo de la pestaña — para no contaminar la sesión
// admin que vive en localStorage. app.js prefiere ese token en getAuthToken().

(function ingestImpersonateHash() {
  try {
    if (typeof window === "undefined" || !window.location) return;
    const match = (window.location.hash || "").match(
      /(?:^#|&)impersonate=([^&]+)/,
    );
    if (!match) return;
    const token = decodeURIComponent(match[1]);
    sessionStorage.setItem("impersonationToken", token);
    // Limpiar el hash sin recargar (el token ya quedó guardado)
    if (window.history && window.history.replaceState) {
      window.history.replaceState(
        null,
        "",
        window.location.pathname + window.location.search,
      );
    }
  } catch (e) {
    /* la ingesta es best-effort: sin hash no hay nada que hacer */
  }
})();

// Banner fijo "Viendo como {estudiante} — Salir" (visible solo si hay token)
function impersonationBanner() {
  return {
    active: false,
    studentName: "",
    studentControl: "",

    init() {
      try {
        this.active = !!sessionStorage.getItem("impersonationToken");
      } catch (e) {
        this.active = false;
      }
      if (!this.active) return;

      // Nombre/control del estudiante desde el perfil (mismo token impersonado)
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      f("/api/auth/profile?type=student")
        .then((r) => (r && r.ok ? r.json() : null))
        .then((data) => {
          if (data && data.student) {
            this.studentName = data.student.full_name || "";
            this.studentControl = data.student.control_number || "";
          }
        })
        .catch(function () {
          /* el banner sigue visible aunque el perfil no cargue */
        });
    },

    exit() {
      if (typeof window.logoutImpersonation === "function") {
        window.logoutImpersonation();
      } else if (typeof window.logout === "function") {
        window.logout();
      }
    },
  };
}

// Modal compartido de impersonación (lado admin). Escucha el evento global
// 'impersonate:request' — que despachan students.js y registrations.js — para
// confirmar y abrir la pestaña del estudiante con el token de corta duración.
function impersonationAdminModal() {
  return {
    active: false,
    target: null, // {id, full_name, control_number}
    busy: false,

    init() {
      window.addEventListener("impersonate:request", (e) => {
        const detail = (e && e.detail) || {};
        if (detail.student && detail.student.id) {
          this.target = detail.student;
          this.active = true;
        }
      });
    },

    close() {
      if (this.busy) return;
      this.active = false;
      this.target = null;
    },

    async confirm() {
      if (!this.target || this.busy) return;
      this.busy = true;
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/admin/impersonate", {
          method: "POST",
          headers: window.getAuthHeaders
            ? window.getAuthHeaders()
            : { "Content-Type": "application/json" },
          body: JSON.stringify({ student_id: this.target.id }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(
            data.message || "Error al generar el token de impersonación",
          );
        }
        // Abrir la pestaña del estudiante con el token en el hash
        // (el fragmento nunca viaja al servidor)
        window.open(
          "/dashboard/student#impersonate=" +
            encodeURIComponent(data.access_token),
          "_blank",
        );
        this.active = false;
        this.target = null;
        if (window.showToast) {
          window.showToast(
            "Sesión del estudiante abierta en una pestaña nueva",
            "success",
          );
        }
      } catch (e) {
        if (window.showToast) {
          window.showToast((e && e.message) || "Error al impersonar", "error");
        }
      } finally {
        this.busy = false;
      }
    },
  };
}

// Exponer globalmente para Alpine (x-data="impersonationBanner()")
if (typeof window !== "undefined") {
  window.impersonationBanner = impersonationBanner;
  window.impersonationAdminModal = impersonationAdminModal;
}

// Exportar para Node/Jest (CommonJS)
if (typeof module !== "undefined" && module.exports) {
  module.exports = { impersonationBanner, impersonationAdminModal };
}
