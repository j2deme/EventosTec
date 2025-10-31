function selfRegister() {
  return {
    activityId: null,
    activityName: null,
    controlNumber: "",
    password: "",
    loading: false,
    message: "",
    messageClass: "bg-green-100 text-green-800",
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
        };
        if (window.__selfRegister_init && el) {
          init = window.__selfRegister_init(el) || init;
        }
        this.activityId = init.id || null;
        this.activityName = init.name || null;
        this.activityExists = !!init.exists;
        this.activityAllowed = !!init.allowed;
        this.activityInvalid = !!init.invalid;

        if (!this.activityExists) {
          this.messageClass = "bg-red-100 text-red-800";
          this.message = "Actividad no encontrada. Contacta al personal.";
        } else if (!this.activityAllowed) {
          this.messageClass = "bg-yellow-100 text-yellow-800";
          this.message =
            "El registro para esta actividad ha finalizado o no está disponible.";
        }

        // expired flag used to hide the form when time ends
        this.expired = false;
        // read activity timing data for countdown
        try {
          const card = document.getElementById("self-register-card");
          const startIso = card?.dataset?.activityStart;
          const duration = card?.dataset?.activityDuration;
          const deadlineIso = card?.dataset?.activityDeadline;

          if (deadlineIso) {
            if (typeof dayjs !== "undefined") {
              this.deadline = dayjs(deadlineIso);
              this.startCountdown();
            }
          } else if (startIso) {
            // compute deadline = start + 20 minutes (self-registration window)
            if (typeof dayjs !== "undefined") {
              const start = dayjs(startIso);
              this.deadline = start.add(20, "minute");
              this.startCountdown();
            }
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

    startCountdown() {
      if (!this.deadline) return;
      // clear existing interval if any
      if (this.countdownInterval) clearInterval(this.countdownInterval);

      const update = () => {
        const now = dayjs();
        const diff = this.deadline.diff(now);
        if (diff <= 0) {
          this.timeLeftText =
            "El tiempo de registro para esta actividad ha finalizado.";
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
