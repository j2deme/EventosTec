function selfRegister() {
  return {
    activityId: null,
    activityToken: null,
    activityName: null,
    controlNumber: "",
    password: "",
    loading: false,
    message: "",
    messageClass: "bg-green-100 text-green-800",

    init() {
      try {
        // Read initial values from the container via helper provided inline
        const el = document.getElementById("self-register-card");
        let init = {
          token: "",
          name: "",
          exists: false,
          provided: false,
          invalid: false,
        };
        if (window.__selfRegister_init && el) {
          init = window.__selfRegister_init(el) || init;
        }
        this.activityToken = init.token || null;
        this.activityName = init.name || null;
        this.activityExists = !!init.exists;
        this.activityTokenProvided = !!init.provided;
        this.activityTokenInvalid = !!init.invalid;

        if (!this.activityExists) {
          if (this.activityTokenProvided && this.activityTokenInvalid) {
            this.messageClass = "bg-yellow-100 text-yellow-800";
            this.message = "Token inválido o expirado. Contacta al personal.";
          } else {
            this.messageClass = "bg-red-100 text-red-800";
            this.message = "Actividad no encontrada o token inválido.";
          }
        }
      } catch (e) {
        /* ignore */
      }
    },

    async submit() {
      this.message = "";
      this.loading = true;
      try {
        if (!this.activityExists) {
          this.messageClass = "bg-red-100 text-red-800";
          this.message =
            "Actividad no disponible. Contacta al módulo de soporte.";
          this.loading = false;
          return;
        }

        const payload = {
          control_number: (this.controlNumber || "").toString().trim(),
          password: this.password,
          activity_token: this.activityToken,
        };
        const resp = await fetch("/api/registrations/self", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await resp.json().catch(() => ({}));
        if (resp.status === 201) {
          this.messageClass = "bg-green-100 text-green-800";
          this.message = data.message || "Registro exitoso";
          this.controlNumber = "";
          this.password = "";
        } else if (resp.status === 409) {
          this.messageClass = "bg-yellow-100 text-yellow-800";
          this.message = data.message || "Ya existe registro";
        } else if (resp.status === 401) {
          this.messageClass = "bg-red-100 text-red-800";
          this.message = data.message || "Credenciales inválidas";
        } else if (resp.status === 400) {
          this.messageClass = "bg-red-100 text-red-800";
          this.message = data.message || "Error en la solicitud";
        } else if (resp.status === 503) {
          this.messageClass = "bg-red-100 text-red-800";
          this.message =
            data.message ||
            "Servicio de validación no disponible. Acude al módulo de soporte.";
        } else {
          this.messageClass = "bg-red-100 text-red-800";
          this.message = data.message || "Error inesperado";
        }
      } catch (e) {
        this.messageClass = "bg-red-100 text-red-800";
        this.message = "Error de red. Reintenta.";
      } finally {
        this.loading = false;
      }
    },
  };
}

// Expose for Alpine when used in template
window.selfRegister = selfRegister;
