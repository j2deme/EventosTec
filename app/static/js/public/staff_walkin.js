/**
 * Registro rápido de staff — /public/staff-walkin/<slug>
 *
 * El HTML vive en `app/templates/public/staff_walkin.html`; este archivo solo
 * expone la factory que Alpine monta con `x-data="staffWalkin()"`.
 *
 * Convención (ver AGENTS.md): los tests Jest mockean `fetch`/`localStorage`
 * ANTES del `require` y usan `jest.resetModules()` entre escenarios.
 */

function staffWalkin() {
  return {
    controlNumber: "",
    activityId: "",
    activityName: "",
    activityStartIso: null,
    staffWindowOpen: true,
    student: {},
    state: "idle", // idle | searching | found | not_found | lookup_error
    // Acción derivada de la búsqueda:
    // 'create' | 'confirm_reg' | 'cancel_reg' | 'cancel_attendance'
    actionMode: null,
    actionTargetId: null,
    message: "",
    msgClass: "",

    // Guard de carreras: el input va con debounce y Enter lanza otra búsqueda,
    // así que en red lenta dos respuestas se solapan. Cada búsqueda toma un
    // número de secuencia y solo aplica si sigue siendo la última.
    _seq: 0,
    // Re-evalúa la ventana de staff sin recargar la página.
    _windowTimer: null,

    init() {
      const card = document.getElementById("staff-walkin-card");
      if (card) {
        this.activityId = card.dataset.activityId || "";
        this.activityName = card.dataset.activityName || "";
        this.activityStartIso =
          card.getAttribute("data-activity-start") || null;
      }
      this._computeStaffWindow();
      // Antes solo se calculaba aquí: con la pestaña abierta la ventana nunca
      // se cerraba y, al iniciar antes del evento, seguía abierta después.
      this._windowTimer = setInterval(
        () => this._computeStaffWindow(),
        30 * 1000,
      );
      this._focusInput();
    },

    /** Limpia el intervalo (lo usan los tests y Alpine al desmontar). */
    destroy() {
      if (this._windowTimer) {
        clearInterval(this._windowTimer);
        this._windowTimer = null;
      }
    },

    _focusInput() {
      this.$nextTick &&
        this.$nextTick(
          () =>
            this.$refs &&
            this.$refs.ctrl &&
            this.$refs.ctrl.focus &&
            this.$refs.ctrl.focus(),
        );
    },

    async lookup() {
      const num = (this.controlNumber || "").trim();
      // require at least 8 characters to reduce external lookups
      if (!num || num.length < 8) {
        this._resetStudent();
        this.state = "idle";
        return;
      }
      if (!this.staffWindowOpen) {
        this.state = "idle";
        return;
      }

      this.state = "searching";
      this.message = "";
      const seq = ++this._seq;

      // 1) Base local (mismo enfoque que registrations_public.js).
      //    Antes se consultaba igualmente el servicio externo aunque hubiera
      //    coincidencia local: +1 petición lenta y, si el externo fallaba o no
      //    lo conocía, se tiraba el match local y decía "no encontrado".
      let localMatch = null;
      try {
        const local = await fetch(
          `/api/students/?search=${encodeURIComponent(num)}&per_page=10`,
        );
        if (local && local.ok) {
          const j = await local.json().catch(() => ({}));
          const students = j.students || [];
          localMatch =
            (students.find &&
              students.find((s) => String(s.control_number) === String(num))) ||
            null;
        }
      } catch (e) {
        console.debug("local lookup failed", e);
      }

      if (seq !== this._seq) return; // búsqueda ya superada

      if (localMatch) {
        this.student = this._normalizeStudent(localMatch, num);
      } else {
        // 2) Fallback externo, solo si no está en la base local.
        let externalStudent = null;
        let notFound = false;
        let failed = false;
        try {
          const ext = await fetch(
            `/api/students/validate?control_number=${encodeURIComponent(num)}`,
          );
          if (ext && ext.ok) {
            const j = await ext.json().catch(() => ({}));
            externalStudent = j.student || null;
            if (!externalStudent) notFound = true;
          } else if (ext && ext.status === 404) {
            notFound = true;
          } else {
            // 503/502/500: el servicio externo no respondió, eso NO significa
            // que el estudiante no exista.
            failed = true;
          }
        } catch (e) {
          console.error("external lookup error", e);
          failed = true;
        }

        if (seq !== this._seq) return;

        if (externalStudent) {
          this.student = this._normalizeStudent(externalStudent, num);
        } else {
          this.actionMode = null;
          this.actionTargetId = null;
          this.student = {};
          if (failed) {
            this.state = "lookup_error";
          } else {
            this.state = "not_found";
          }
          return;
        }
      }

      if (seq !== this._seq) return;

      // 3) Registros/asistencias de esta actividad -> acción a ofrecer.
      let match = null;
      if (this.activityId) {
        try {
          const qs = new URLSearchParams();
          qs.set("activity_id", this.activityId);
          qs.set("q", num);
          qs.set("per_page", "20");
          const resp = await fetch(
            `/api/public/registrations?${qs.toString()}`,
          );
          if (resp && resp.ok) {
            const j = await resp.json().catch(() => ({}));
            const regs = j.registrations || [];
            // Solo coincidencia EXACTA de número de control. El `q` del
            // backend filtra por subcadena (control o nombre) y el antiguo
            // fallback `regs[0]` podía devolver el registro de OTRO
            // estudiante, con el que se confirmaba/marcaba ausente.
            match =
              (regs.find &&
                regs.find((r) => String(r.control_number) === String(num))) ||
              null;
          }
        } catch (e) {
          console.debug("registrations check failed", e);
        }
        if (seq !== this._seq) return;
      }

      if (match) {
        if (match.source === "registration") {
          if (match.attended) {
            // ya confirmó -> ofrecer marcar Ausente
            this.actionMode = "cancel_reg";
            this.actionTargetId = match.registration_id || match.id || null;
          } else {
            // preregistrado sin asistir -> ofrecer confirmar
            this.actionMode = "confirm_reg";
            this.actionTargetId = match.registration_id || match.id || null;
          }
          this.state = "found";
          return;
        }
        if (match.source === "attendance" && match.attended) {
          this.actionMode = "cancel_attendance";
          this.actionTargetId = match.attendance_id || null;
          this.state = "found";
          return;
        }
      }

      // Sin registro/asistencia -> permitir crear walk-in
      this.actionMode = "create";
      this.actionTargetId = null;
      this.state = "found";
    },

    _resetStudent() {
      this.student = {};
      this.actionMode = null;
      this.actionTargetId = null;
    },

    _normalizeStudent(source, fallbackControl) {
      return {
        full_name: source.full_name || source.name || "",
        career: source.career || "",
        email: source.email || "",
        control_number: source.control_number || fallbackControl,
      };
    },

    _computeStaffWindow() {
      try {
        // staff window: de AHORA hasta activity_start + 25 minutos.
        // Si la fecha es desconocida o inválida, queda abierta.
        if (!this.activityStartIso) {
          this.staffWindowOpen = true;
          return;
        }
        const start = new Date(this.activityStartIso);
        if (isNaN(start.getTime())) {
          this.staffWindowOpen = true;
          return;
        }
        const now = new Date();
        const until = new Date(start.getTime() + 25 * 60 * 1000);
        this.staffWindowOpen = now <= until;
      } catch (e) {
        console.error("compute staff window error", e);
        this.staffWindowOpen = true;
      }
    },

    /** Toast con el número de control delante para identificar al alumno. */
    _showResultToast(msg, level) {
      const ctrl =
        this.controlNumber ||
        (this.student && this.student.control_number) ||
        "";
      const full = ctrl ? `[${ctrl}] ${msg}` : msg;
      try {
        showToast(full, level);
      } catch (e) {
        alert(full);
      }
    },

    _onActionSuccess(msg) {
      // El toast va ANTES de limpiar: clearSearch vacía controlNumber/student.
      this._showResultToast(msg, "success");
      this.clearSearch();
      // ...y el mensaje va DESPUÉS, porque clearSearch lo borra: antes el
      // aviso en pantalla nunca se llegaba a ver.
      this.message = msg;
      this.msgClass = "text-green-600";
    },

    _onActionError(msg) {
      this._showResultToast(msg, "error");
      this.message = msg;
      this.msgClass = "text-red-600";
    },

    // Unified action handler: perform confirm/create or cancel depending on actionMode
    async performAction() {
      if (!this.actionMode) return;

      // Re-evalúa la ventana antes de actuar: una pestaña abierta desde
      // antes no podía cerrarse sola.
      this._computeStaffWindow();
      if (!this.staffWindowOpen) {
        this._onActionError("El período de registro por staff ha finalizado.");
        return;
      }

      // Invalida cualquier búsqueda en vuelo (evita que la ficha reaparezca
      // sobre el resultado de la acción).
      this._seq++;

      try {
        if (this.actionMode === "create") {
          if (
            !confirm(
              "Confirmar asistencia para " +
                (this.student.full_name || this.controlNumber) +
                "?",
            )
          )
            return;
          const payload = {
            activity_id: this.activityId,
            control_number:
              (this.student && this.student.control_number) ||
              this.controlNumber,
          };
          const res = await fetch("/api/public/registrations/walkin", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          const body = await res.json().catch(() => ({}));
          if (res.ok || res.status === 201) {
            this._onActionSuccess(body.message || "Asistencia registrada");
          } else {
            this._onActionError(body.message || "Error al registrar");
          }
        } else if (this.actionMode === "confirm_reg") {
          if (!this.actionTargetId) return;
          if (
            !confirm(
              "Confirmar asistencia para " +
                (this.student.full_name || this.controlNumber) +
                "?",
            )
          )
            return;
          const res = await fetch(
            `/api/public/registrations/${this.actionTargetId}/confirm`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                activity_id: this.activityId,
                confirm: true,
                create_attendance: true,
              }),
            },
          );
          const body = await res.json().catch(() => ({}));
          if (res.ok) {
            this._onActionSuccess(body.message || "Asistencia confirmada");
          } else {
            this._onActionError(body.message || "Error al confirmar");
          }
        } else if (this.actionMode === "cancel_reg") {
          if (!this.actionTargetId) return;
          if (
            !confirm(
              "¿Desea marcar como AUSENTE a " +
                (this.student.full_name || this.controlNumber) +
                "? Esta acción se registrará como Ausente.",
            )
          )
            return;
          const res = await fetch(
            `/api/public/registrations/${this.actionTargetId}/confirm`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                activity_id: this.activityId,
                confirm: false,
                create_attendance: false,
                mark_absent: true,
              }),
            },
          );
          const body = await res.json().catch(() => ({}));
          if (res.ok) {
            this._onActionSuccess(
              body.message || "Registro marcado como Ausente",
            );
          } else {
            this._onActionError(body.message || "Error al actualizar");
          }
        } else if (this.actionMode === "cancel_attendance") {
          if (!this.actionTargetId) return;
          if (
            !confirm(
              "¿Desea eliminar la asistencia registrada para " +
                (this.student.full_name || this.controlNumber) +
                "?",
            )
          )
            return;
          const res = await fetch(
            `/api/public/attendances/${this.actionTargetId}/toggle`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                activity_id: this.activityId,
                confirm: false,
              }),
            },
          );
          const body = await res.json().catch(() => ({}));
          if (res.ok) {
            this._onActionSuccess(body.message || "Asistencia removida");
          } else {
            this._onActionError(body.message || "Error al eliminar asistencia");
          }
        }
      } catch (e) {
        console.error("performAction error", e);
        this.message = "Error de conexión";
        this.msgClass = "text-red-600";
      }
    },

    clearSearch() {
      // Invalida búsquedas en vuelo: si no, la respuesta llegaba después de
      // "Limpiar" y repintaba la ficha del estudiante.
      this._seq++;
      this.controlNumber = "";
      this._resetStudent();
      this.state = "idle";
      this.message = "";
      this._focusInput();
    },
  };
}

// Expose for Alpine when used in template
if (typeof window !== "undefined") window.staffWalkin = staffWalkin;
