// Modal de cambio de contraseña (solo administradores).
//
// La contraseña de los admins vive en la BD local (users.password_hash), no en
// la plataforma MAB, así que este modal habla directo con
// POST /api/auth/change-password.
//
// Se abre despachando el evento global 'change-password:open' (patrón usado ya
// por attendances.html con 'open-sync-modal'): el menú de usuario de
// admin/base.html hace $dispatch(...) y el componente lo escucha en init().
function changePasswordModal() {
  return {
    active: false,
    busy: false,
    error: "",
    showPasswords: false,
    form: { current: "", next: "", confirm: "" },

    init() {
      window.addEventListener("change-password:open", () => this.open());
    },

    open() {
      this.error = "";
      this.showPasswords = false;
      this.form = { current: "", next: "", confirm: "" };
      this.active = true;
    },

    close() {
      if (this.busy) return;
      this.active = false;
      this.error = "";
    },

    // Validación en cliente; el backend vuelve a validar todo (es la fuente de
    // verdad) y agrega el rate-limit y la verificación de la contraseña actual.
    validate() {
      const { current, next, confirm } = this.form;
      if (!current || !next || !confirm) {
        return "Los tres campos son requeridos.";
      }
      if (next.length < 8) {
        return "La nueva contraseña debe tener al menos 8 caracteres.";
      }
      if (next !== confirm) {
        return "La confirmación no coincide con la nueva contraseña.";
      }
      if (next === current) {
        return "La nueva contraseña debe ser distinta de la actual.";
      }
      return "";
    },

    async submit() {
      const problem = this.validate();
      if (problem) {
        this.error = problem;
        return;
      }
      if (this.busy) return;

      this.busy = true;
      this.error = "";
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/auth/change-password", {
          method: "POST",
          headers: window.getAuthHeaders
            ? window.getAuthHeaders()
            : { "Content-Type": "application/json" },
          body: JSON.stringify({
            current_password: this.form.current,
            new_password: this.form.next,
            confirm_password: this.form.confirm,
          }),
        });
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          // 400 (contraseña actual incorrecta / validaciones), 429 (rate-limit)
          // o 500: el backend ya mandó un mensaje usable.
          this.error = data.message || "No se pudo cambiar la contraseña.";
          return;
        }

        this.form = { current: "", next: "", confirm: "" };
        this.active = false;
        if (window.showToast) {
          window.showToast(
            data.message || "Contraseña actualizada correctamente.",
            "success",
          );
        }
      } catch (e) {
        this.error = "Error de conexión. Intenta de nuevo.";
      } finally {
        this.busy = false;
      }
    },
  };
}

// Exponer globalmente para Alpine (x-data="changePasswordModal()")
if (typeof window !== "undefined") {
  window.changePasswordModal = changePasswordModal;
}

// Exportar para Node/Jest (CommonJS)
if (typeof module !== "undefined" && module.exports) {
  module.exports = { changePasswordModal };
}
