function selfRegister() {
  return {
    activityId: null,
    activityName: null,
    controlNumber: "",
    password: "",
    loading: false,
    verifyOnly: false,
    checkedIn: false,
    successDetail: "",
    message: "",
    messageClass: "bg-green-100 text-green-800",
    unavailableMessage:
      "El auto-registro para esta actividad ha finalizado o no está disponible.",
    countdownInterval: null,
    timeLeftText: "",
    deadline: null,

    init() {
      try {
        // Read initial values from the container via helper provided inline
        const el = document.getElementById("self-register-card");
        let init = {
          id: "",
          name: "",
          exists: false,
          allowed: true,
          invalid: false,
          message: "",
        };
        if (window.__selfRegister_init && el) {
          init = window.__selfRegister_init(el) || init;
        }
        this.activityId = init.id || null;
        this.activityName = init.name || null;
        this.activityExists = !!init.exists;
        this.activityAllowed = !!init.allowed;
        this.activityInvalid = !!init.invalid;
        // Ventana cerrada: el form se muestra solo para verificar asistencia.
        this.verifyOnly = !!init.verify;

        if (!this.activityExists) {
          this.messageClass = "bg-red-100 text-red-800";
          this.message = "Actividad no encontrada. Contacta al personal.";
        } else if (!this.activityAllowed) {
          this.messageClass = "bg-yellow-100 text-yellow-800";
          // Mensaje del servidor: distingue "aún no abre" de "ya cerró".
          this.unavailableMessage = init.message || this.unavailableMessage;
          // En modo verificación el banner ya muestra ese texto; no duplicar.
          if (!this.verifyOnly) this.message = this.unavailableMessage;
        }

        // expired flag used to hide the form when time ends
        this.expired = false;
        // read activity timing data for countdown
        try {
          const card = document.getElementById("self-register-card");
          const deadlineIso = card?.dataset?.activityDeadline;

          // El deadline lo calcula el backend (ventana configurable); no se
          // deriva en el cliente para evitar que diverjan.
          if (deadlineIso && typeof dayjs !== "undefined") {
            this.deadline = dayjs(deadlineIso);
            this.startCountdown();
          }
        } catch (e) {
          // ignore - countdown is optional
          console.error("countdown init error", e);
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
          activity_id: this.activityId,
        };
        const resp = await fetch("/api/registrations/self", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await resp.json().catch(() => ({}));
        if (resp.status === 201) {
          this.markCheckedIn(data);
        } else if (resp.status === 409) {
          if (data.code === "already_registered") {
            // Mismo estado que el 201: ya estaba registrado, no es un error.
            this.markCheckedIn(data);
          } else {
            this.messageClass = "bg-yellow-100 text-yellow-800";
            this.message =
              data.message || "Ya registraste tu asistencia en esta actividad";
          }
        } else if (resp.status === 401) {
          this.messageClass = "bg-red-100 text-red-800";
          this.message = data.message || "Credenciales inválidas";
        } else if (resp.status === 429) {
          this.messageClass = "bg-yellow-100 text-yellow-800";
          this.message =
            data.message ||
            "Demasiados intentos. Espera unos minutos y vuelve a intentarlo.";
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

    // Pantalla de confirmación: se usa tanto en el 201 (primer check-in)
    // como en el 409 "ya registrado", para que el estudiante salga con la
    // misma certeza en ambos casos.
    markCheckedIn(data) {
      const attendance = (data && data.attendance) || {};
      const time = this.formatCheckInTime(attendance.check_in_time);
      this.successDetail = time
        ? `Entrada: ${time}`
        : "Tu asistencia quedó registrada.";
      this.message = "";
      this.checkedIn = true;
      this.controlNumber = "";
      this.password = "";
    },

    formatCheckInTime(value) {
      if (!value) return "";
      try {
        if (
          window.dateHelpers &&
          typeof window.dateHelpers.formatTime === "function"
        ) {
          return window.dateHelpers.formatTime(value);
        }
      } catch (e) {
        // sin dateHelpers (tests / carga parcial): fallback abajo
      }
      const raw = String(value);
      return raw.length >= 16 ? raw.slice(11, 16) : "";
    },

    // "Continuar" en la tarjeta de éxito: limpia la confirmación y vuelve al
    // formulario (en modo verificación si la ventana ya cerró).
    continueFromSuccess() {
      this.checkedIn = false;
      this.successDetail = "";
      this.message = "";
      this.controlNumber = "";
      this.password = "";
    },

    startCountdown() {
      if (!this.deadline) return;
      // clear existing interval if any
      if (this.countdownInterval) clearInterval(this.countdownInterval);

      const update = () => {
        const now = dayjs();
        const diff = this.deadline.diff(now);
        if (diff <= 0) {
          this.timeLeftText =
            "El auto-registro para esta actividad ha finalizado.";
          // hide the form and show an expired notice
          this.expired = true;
          const frm = document.getElementById("self-register-form");
          if (frm) frm.style.display = "none";
          clearInterval(this.countdownInterval);
          this.countdownInterval = null;
          return;
        }

        // Prefer using dayjs.duration when available (plugin), otherwise fallback to manual calculation
        let text = "";
        const totalSec = Math.ceil(diff / 1000);
        if (typeof dayjs.duration === "function") {
          try {
            const dur = dayjs.duration(diff);
            const hours = Math.floor(dur.asHours());
            const minutes = dur.minutes();
            if (dur.asHours() >= 1) {
              text = hours === 1 ? "1 hora" : `${hours} horas`;
              if (minutes > 0)
                text += `, ${minutes} ${minutes === 1 ? "minuto" : "minutos"}`;
              text += " restantes";
            } else if (totalSec >= 60) {
              const mins = Math.ceil(totalSec / 60);
              text =
                mins === 1 ? "1 minuto restante" : `${mins} minutos restantes`;
            } else {
              text =
                totalSec === 1
                  ? "1 segundo restante"
                  : `${totalSec} segundos restantes`;
            }
          } catch (e) {
            // fallback to manual if duration call fails
            if (totalSec >= 3600) {
              const hours = Math.floor(totalSec / 3600);
              const minutes = Math.floor((totalSec % 3600) / 60);
              text = hours === 1 ? "1 hora" : `${hours} horas`;
              if (minutes > 0)
                text += `, ${minutes} ${minutes === 1 ? "minuto" : "minutos"}`;
              text += " restantes";
            } else if (totalSec >= 60) {
              const minutes = Math.ceil(totalSec / 60);
              text =
                minutes === 1
                  ? "1 minuto restante"
                  : `${minutes} minutos restantes`;
            } else {
              text =
                totalSec === 1
                  ? "1 segundo restante"
                  : `${totalSec} segundos restantes`;
            }
          }
        } else {
          // Manual fallback (no duration plugin available)
          if (totalSec >= 3600) {
            const hours = Math.floor(totalSec / 3600);
            const minutes = Math.floor((totalSec % 3600) / 60);
            text = hours === 1 ? "1 hora" : `${hours} horas`;
            if (minutes > 0)
              text += `, ${minutes} ${minutes === 1 ? "minuto" : "minutos"}`;
            text += " restantes";
          } else if (totalSec >= 60) {
            const minutes = Math.ceil(totalSec / 60);
            text =
              minutes === 1
                ? "1 minuto restante"
                : `${minutes} minutos restantes`;
          } else {
            text =
              totalSec === 1
                ? "1 segundo restante"
                : `${totalSec} segundos restantes`;
          }
        }

        this.timeLeftText = text;
      };

      update();
      this.countdownInterval = setInterval(update, 1000);
    },
  };
}

// Expose for Alpine when used in template
window.selfRegister = selfRegister;
