function registrationsPublic() {
  return {
    token: null,
    activityName: null,
    activityType: null,
    deadline: null,
    start: null,
    end: null,
    activityDateRange: null,
    activityLocation: null,
    activityModality: null,
    eventName: null,
    eventId: null,
    eventToken: null,
    timeLeftText: "",
    regs: [],
    controlsEnabled: false,
    registerState: "open", // 'pending' | 'open' | 'closed'
    page: 1,
    per_page: 50,
    total: 0,
    q: "",
    showWalkin: false,
    // Confirm-delete modal state
    showConfirmDelete: false,
    deleteCandidate: null,
    // Undo toast state
    undoVisible: false,
    undoDuration: 5000,
    undoRemaining: 0,
    _undoInterval: null,
    _undoTimeout: null,
    pendingDeleteId: null,
    _lastRemoved: null,
    walkin: { control_number: "", full_name: "", email: "", career: "" },
    walkinLookupState: "idle", // idle | searching | found | not_found | error
    walkinFoundSource: null, // null | 'local' | 'external'

    init() {
      try {
        const el = document.getElementById("public-registrations-card");
        const init =
          window.__registrationsPublic_init && el
            ? window.__registrationsPublic_init(el)
            : { token: "", name: "", type: "", deadline: "" };
        this.token = init.token || null;
        this.activityName = init.name || null;
        this.activityType = init.type || null;
        this.deadline = init.deadline || null;
        this.start = init.start || null;
        this.end = init.end || null;
        this.activityLocation = init.location || null;
        this.activityModality = init.modality || null;
        this.eventName = init.eventName || null;
        this.eventId = init.eventId || null;
        this.eventToken = init.eventToken || null;

        // compute human-friendly date range
        try {
          if (this.start && typeof dayjs !== "undefined") {
            const s = dayjs(this.start);
            const e = this.end ? dayjs(this.end) : null;
            if (e) {
              if (s.isSame(e, "day")) {
                this.activityDateRange = s.format("D MMM YYYY");
              } else {
                this.activityDateRange =
                  s.format("D MMM YYYY") + " — " + e.format("D MMM YYYY");
              }
            } else {
              this.activityDateRange = s.format("D MMM YYYY");
            }
          }
        } catch (e) {
          this.activityDateRange = null;
        }
        this.fetchRegs();
        this.initCountdown();
      } catch (e) {
        console.error("init error", e);
      }
    },

    initCountdown() {
      try {
        if (typeof dayjs === "undefined") return;

        // parse start/deadline into dayjs objects if present
        const start = this.start ? dayjs(this.start) : null;
        const deadline = this.deadline ? dayjs(this.deadline) : null;

        // Clear any existing interval handle stored on the component
        if (this._countdownHandle) {
          clearInterval(this._countdownHandle);
          this._countdownHandle = null;
        }

        const formatUnit = (value, singular, plural) =>
          `${value} ${value === 1 ? singular : plural}`;

        const buildUnits = (duration) => {
          const years = Math.floor(duration.asYears());
          const months = Math.floor(duration.asMonths() % 12);
          const weeks = Math.floor(duration.asWeeks() % 4);
          const days = Math.floor(duration.asDays() % 7);
          const hours = duration.hours();
          const minutes = duration.minutes();
          const seconds = duration.seconds();
          return [
            [years, "año", "años"],
            [months, "mes", "meses"],
            [weeks, "semana", "semanas"],
            [days, "día", "días"],
            [hours, "hora", "horas"],
            [minutes, "minuto", "minutos"],
            [seconds, "segundo", "segundos"],
          ];
        };

        const pickSignificant = (duration, maxParts = 2) => {
          const units = buildUnits(duration);
          const parts = [];
          for (let i = 0; i < units.length && parts.length < maxParts; i++) {
            const [value, singular, plural] = units[i];
            if (value && value > 0) {
              parts.push(formatUnit(value, singular, plural));
            }
          }
          if (parts.length === 0) {
            const s = Math.max(0, Math.floor(duration.asSeconds()));
            parts.push(formatUnit(s, "segundo", "segundos"));
          }
          return parts.join(" y ");
        };

        // adaptive tick chooser reused from before
        const chooseIntervalMs = (diffMs) => {
          const diffSec = diffMs / 1000;
          const diffMin = diffSec / 60;
          const diffHour = diffMin / 60;
          const diffDay = diffHour / 24;
          const diffWeek = diffDay / 7;
          const diffMonth = diffDay / 30;

          if (diffMin < 1) return 1000; // update each second
          if (diffHour < 1) return 15 * 1000; // update each 15s
          if (diffDay < 1) return 60 * 1000; // update each 1m
          if (diffWeek < 1) return 5 * 60 * 1000; // update each 5m
          if (diffMonth < 1) return 60 * 60 * 1000; // update each 1h
          return 6 * 60 * 60 * 1000; // update each 6h for long durations
        };

        const updateOnce = () => {
          const now = dayjs();

          // If there's a start and we're before it, show time until start and disable controls
          if (start && now.isBefore(start)) {
            this.controlsEnabled = false;
            const d = dayjs.duration(start.diff(now));
            this.timeLeftText = `Registro de asistencias inicia en ${pickSignificant(
              d,
              2
            )}`;
            return start.diff(now);
          }

          // Activity started (or no explicit start): enable controls unless already past deadline
          this.controlsEnabled = true;

          if (deadline) {
            const diffMs = deadline.diff(now);
            if (diffMs <= 0) {
              this.controlsEnabled = false;
              this.timeLeftText = "El registro de asistencias ha cerrado";
              return diffMs;
            }
            const d = dayjs.duration(diffMs);
            this.timeLeftText = `El registro de asistencias cierra en ${pickSignificant(
              d,
              2
            )}`;
            return diffMs;
          }

          // No deadline: just indicate opened
          this.timeLeftText = "Registro de asistencias abierto";
          return 60 * 1000; // arbitrary 1m tick
        };

        // initial update and scheduling similar to previous logic
        let diffMs = updateOnce();

        const schedule = () => {
          if (this._countdownHandle) {
            clearInterval(this._countdownHandle);
            this._countdownHandle = null;
          }
          const nextInterval = chooseIntervalMs(Math.max(0, diffMs));
          this._countdownHandle = setInterval(() => {
            try {
              diffMs = updateOnce();
              if (diffMs <= 0) {
                clearInterval(this._countdownHandle);
                this._countdownHandle = null;
                return;
              }
              const desired = chooseIntervalMs(diffMs);
              if (desired !== nextInterval) {
                schedule();
              }
            } catch (e) {
              console.error("countdown tick error", e);
            }
          }, nextInterval);
        };

        schedule();
      } catch (e) {
        console.error("countdown init error", e);
      }
    },

    async fetchRegs() {
      try {
        const qs = new URLSearchParams();
        if (this.token) qs.set("token", this.token);
        if (this.q) qs.set("q", this.q);
        qs.set("page", String(this.page));
        qs.set("per_page", String(this.per_page));
        const resp = await fetch(`/api/public/registrations?${qs.toString()}`);
        if (!resp.ok) {
          const json = await resp.json().catch(() => ({}));
          this.message = json.message || "Error";
          return;
        }
        const data = await resp.json();
        this.regs = data.registrations || [];
        // Ordenar por número de control ascendente si existe el campo
        try {
          this.regs.sort((a, b) => {
            const ac =
              a.control_number == null
                ? ""
                : String(a.control_number).padStart(20, "0");
            const bc =
              b.control_number == null
                ? ""
                : String(b.control_number).padStart(20, "0");
            if (ac < bc) return -1;
            if (ac > bc) return 1;
            return 0;
          });
        } catch (e) {
          console.error("sort regs error", e);
        }
        this.total = data.total || 0;
      } catch (e) {
        console.error("fetchRegs error", e);
      }
    },

    prevPage() {
      if (this.page > 1) {
        this.page--;
        this.fetchRegs();
      }
    },
    nextPage() {
      if (this.page * this.per_page < this.total) {
        this.page++;
        this.fetchRegs();
      }
    },

    async confirm(r) {
      try {
        const payload = {
          token: this.token,
          confirm: true,
          create_attendance: true,
        };
        const resp = await fetch(`/api/public/registrations/${r.id}/confirm`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const json = await resp.json().catch(() => ({}));
        if (resp.ok) {
          this.fetchRegs();
          try {
            showToast("Confirmado", "success");
          } catch (e) {
            alert("Confirmado");
          }
        } else {
          try {
            showToast(json.message || "Error", "error");
          } catch (e) {
            alert(json.message || "Error");
          }
        }
      } catch (e) {
        console.error("confirm error", e);
      }
    },

    async reject(r) {
      try {
        const payload = {
          token: this.token,
          confirm: false,
          create_attendance: false,
        };
        const resp = await fetch(`/api/public/registrations/${r.id}/confirm`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const json = await resp.json().catch(() => ({}));
        if (resp.ok) {
          this.fetchRegs();
          try {
            showToast("Marcado como no asistió", "success");
          } catch (e) {
            alert("Marcado como no asistió");
          }
        } else {
          try {
            showToast(json.message || "Error", "error");
          } catch (e) {
            alert(json.message || "Error");
          }
        }
      } catch (e) {
        console.error("reject error", e);
      }
    },

    async toggleAttendance(r, ev) {
      try {
        if (!this.controlsEnabled) {
          try {
            showToast("El registro de asistencias aún no inicia", "info");
          } catch (e) {}
          return;
        }
        // derive new checked state as toggle of current
        const checked = !Boolean(r.attended);

        // Hybrid: show spinner immediately but avoid changing the badge until
        // the server confirms. Store previous values for rollback.
        r._toggling = true;
        const previous = !!r.attended;
        const previousStatus = r.status;
        const previousConfirmationDate = r.confirmation_date || null;

        const payload = {
          token: this.token,
          confirm: checked,
          create_attendance: checked,
        };

        // No artificial delay here: send the request right away while spinner
        // indicates progress. The UI badge will update only on success.
        const resp = await fetch(`/api/public/registrations/${r.id}/confirm`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const json = await resp.json().catch(() => ({}));

        if (resp.ok) {
          try {
            const ctrlRaw = r.control_number || "";
            const ctrl = String(ctrlRaw).trim();
            const suffix = ctrl ? `: ${ctrl}` : "";
            showToast(
              checked
                ? `Asistencia registrada${suffix}`
                : `Asistencia removida${suffix}`,
              "success"
            );
          } catch (e) {
            /* fallback */
          }
          // Update the attendance/badge only after server confirmation.
          if (json && json.registration) {
            Object.assign(r, json.registration);
          } else {
            // No registration object returned; apply minimal changes
            // deterministically based on the action.
            r.attended = checked;
            r.status = checked ? "Confirmado" : "Registrado";
            r.confirmation_date = checked ? new Date().toISOString() : null;
          }
        } else {
          console.error("toggleAttendance server error", resp.status, json);
          try {
            showToast(
              json.message || "Error al actualizar asistencia",
              "error"
            );
          } catch (e) {
            /* fallback */
          }
          // Roll back (nothing was applied to badge yet, but restore in case)
          r.attended = previous;
          r.status = previousStatus;
          r.confirmation_date = previousConfirmationDate;
        }

        r._toggling = false;
        // minimal refresh
        setTimeout(() => this.fetchRegs(), 300);
      } catch (e) {
        console.error("toggleAttendance error", e);
        try {
          showToast("Error de red", "error");
        } catch (e) {
          /* fallback */
        }
        // Roll back optimistic changes on unexpected exceptions
        r.attended = previous;
        r.status = previousStatus;
        r.confirmation_date = previousConfirmationDate;
        r._toggling = false;
      }
    },

    async deleteAttendance(attendance_id) {
      try {
        const payload = { token: this.token, confirm: false };
        const resp = await fetch(
          `/api/public/attendances/${attendance_id}/toggle`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }
        );
        const json = await resp.json().catch(() => ({}));
        if (resp.ok) {
          try {
            showToast("Asistencia eliminada", "success");
          } catch (e) {}
          this.fetchRegs();
        } else {
          try {
            showToast(json.message || "Error", "error");
          } catch (e) {}
        }
      } catch (e) {
        console.error("deleteAttendance error", e);
      }
    },

    // Modal controls for deletion with undo
    cancelDeleteModal() {
      // If user cancels the confirmation modal, revert the checkbox visually
      // by restoring the `attended` flag on the original row instead of
      // refetching the entire list. Also clear any _removing flag so the
      // leave transition is cancelled.
      if (this.deleteCandidate) {
        try {
          this.deleteCandidate._removing = false;
          this.deleteCandidate.attended = true;
        } catch (e) {
          // fallback to full refresh if something goes wrong
          this.fetchRegs();
        }
      }
      this.showConfirmDelete = false;
      this.deleteCandidate = null;
    },

    confirmDeleteInModal() {
      if (!this.deleteCandidate || !this.deleteCandidate.attendance_id) {
        this.showConfirmDelete = false;
        this.deleteCandidate = null;
        return;
      }
      // Do not allow multiple pending deletes simultaneously
      if (this.undoVisible) {
        try {
          showToast("Espere a que finalice la acción previa", "info");
        } catch (e) {}
        this.showConfirmDelete = false;
        this.deleteCandidate = null;
        this.fetchRegs();
        return;
      }

      const aid = this.deleteCandidate.attendance_id;
      // find and stash the removed item and its index so we can restore it
      const idx = this.regs.findIndex((r) => r.attendance_id === aid);
      if (idx !== -1) {
        // shallow clone to avoid accidental reference mutation
        try {
          this._lastRemoved = {
            item: JSON.parse(JSON.stringify(this.regs[idx])),
            index: idx,
          };
        } catch (e) {
          // if cloning fails, fallback to storing reference
          this._lastRemoved = { item: this.regs[idx], index: idx };
        }
      } else {
        this._lastRemoved = null;
      }

      this.showConfirmDelete = false;
      // mark row as removing so Alpine can run the leave transition
      const row = this.regs.find((r) => r.attendance_id === aid);
      if (row) row._removing = true;

      // after a short delay (matching the transition duration) remove from array
      setTimeout(() => {
        this.regs = this.regs.filter((r) => r.attendance_id !== aid);
      }, 220);

      // show undo toast and start timer to perform final delete
      this.startUndoTimer(aid);
      this.deleteCandidate = null;
    },

    startUndoTimer(attendance_id) {
      this.pendingDeleteId = attendance_id;
      this.undoRemaining = this.undoDuration;
      this.undoVisible = true;

      // update every second
      this._undoInterval = setInterval(() => {
        this.undoRemaining = Math.max(0, this.undoRemaining - 1000);
      }, 1000);

      this._undoTimeout = setTimeout(async () => {
        // perform the actual deletion on server
        try {
          await this.deleteAttendance(attendance_id);
        } catch (e) {
          console.error("error in scheduled delete", e);
        }
        // cleanup
        this.undoVisible = false;
        this.pendingDeleteId = null;
        // final delete succeeded (or at least attempted). clear stash.
        this._lastRemoved = null;
        if (this._undoInterval) {
          clearInterval(this._undoInterval);
          this._undoInterval = null;
        }
        this._undoTimeout = null;
      }, this.undoDuration);
    },

    async undoDelete() {
      // cancel scheduled deletion
      if (this._undoTimeout) {
        clearTimeout(this._undoTimeout);
        this._undoTimeout = null;
      }
      if (this._undoInterval) {
        clearInterval(this._undoInterval);
        this._undoInterval = null;
      }
      this.undoVisible = false;
      this.pendingDeleteId = null;
      // Restore the removed item locally in its previous position if we have it
      if (this._lastRemoved && this._lastRemoved.item) {
        const idx = this._lastRemoved.index;
        // ensure index is within bounds
        const insertAt = Math.min(Math.max(0, idx), this.regs.length);
        try {
          // Insert a clone so we don't keep references to old objects
          const item = JSON.parse(JSON.stringify(this._lastRemoved.item));
          // Start hidden/removing so enter transition will play when we clear it
          item._removing = true;
          this.regs.splice(insertAt, 0, item);
          // next tick: replace the inserted element with a fresh clone that has _removing=false
          setTimeout(() => {
            try {
              const fresh = JSON.parse(JSON.stringify(item));
              fresh._removing = false;
              // replace at the same index to trigger reactivity
              this.regs.splice(insertAt, 1, fresh);
              // ensure array reactive update
              this.regs = this.regs.slice();
            } catch (e) {
              // if replacement fails, at least clear the flag on the current item
              try {
                const cur = this.regs[insertAt];
                if (cur) cur._removing = false;
              } catch (e2) {}
            }
          }, 40);
        } catch (e) {
          // fallback: push to end
          this.regs.push(this._lastRemoved.item);
        }
        this._lastRemoved = null;
      } else {
        // no stash available: do a full refresh
        this.fetchRegs();
      }
    },

    async onToggleRow(r) {
      // If row has registration_id, use existing toggle flow
      if (r.registration_id) {
        return this.toggleAttendance(r);
      }

      // If row is an attendance-only row and currently attended, toggling will attempt to remove it
      if (r.source === "attendance" && r.attended && r.attendance_id) {
        // Open custom modal to confirm delete with undo option
        this.deleteCandidate = r;
        this.showConfirmDelete = true;
        return;
      }

      // Otherwise, do nothing
      return;
    },

    openWalkin() {
      this.walkin = {
        control_number: "",
        full_name: "",
        email: "",
        career: "",
      };
      this.walkinLookupState = "idle";
      this.walkinFoundSource = null;
      this.showWalkin = true;
    },
    closeWalkin() {
      this.showWalkin = false;
    },

    async lookupWalkin() {
      try {
        const control = (this.walkin.control_number || "").trim();
        if (!control) {
          try {
            showToast("Ingrese número de control", "info");
          } catch (e) {
            alert("Ingrese número de control");
          }
          return;
        }
        // start searching: clear any previous found data to avoid confusion
        this.walkin.full_name = "";
        this.walkin.email = "";
        this.walkinFoundSource = null;
        this.walkinLookupState = "searching";

        // First try local search endpoint (exact match)
        const local = await fetch(
          `/api/students/?search=${encodeURIComponent(control)}&per_page=1`
        );
        if (local && local.ok) {
          const j = await local.json().catch(() => ({}));
          const students = j.students || [];
          // try exact control_number match
          const exact =
            (students.find &&
              students.find(
                (s) => String(s.control_number) === String(control)
              )) ||
            null;
          if (exact) {
            this.walkin.full_name = exact.full_name || "";
            this.walkin.email = exact.email || "";
            this.walkin.career = exact.career || "";
            this.walkinLookupState = "found";
            this.walkinFoundSource = "local";
            return;
          }
        }

        // If not found locally, fallback to external proxy
        try {
          const ext = await fetch(
            `/api/students/validate?control_number=${encodeURIComponent(
              control
            )}`
          );
          if (ext && ext.ok) {
            const j = await ext.json().catch(() => ({}));
            const student = j.student || null;
            if (student) {
              this.walkin.full_name = student.full_name || "";
              this.walkin.email = student.email || "";
              this.walkin.career = student.career || "";
              this.walkinLookupState = "found";
              this.walkinFoundSource = "external";
              return;
            }
            this.walkinLookupState = "not_found";
            return;
          } else if (ext && ext.status === 404) {
            this.walkinLookupState = "not_found";
            // keep displayed fields cleared to avoid showing stale data
            this.walkin.full_name = "";
            this.walkin.email = "";
            this.walkin.career = "";
            this.walkinFoundSource = null;
            try {
              showToast("Estudiante no encontrado", "error");
            } catch (e) {
              /* fallback silent */
            }
            return;
          } else {
            this.walkinLookupState = "error";
            try {
              showToast("Error consultando servicio externo", "error");
            } catch (e) {
              /* fallback silent */
            }
            return;
          }
        } catch (e) {
          console.error("external lookup error", e);
          this.walkinLookupState = "error";
          try {
            showToast("Error consultando servicio externo", "error");
          } catch (e2) {
            /* fallback silent */
          }
          return;
        }
      } finally {
        // noop
      }
    },

    async doWalkin() {
      try {
        if (!this.controlsEnabled) {
          try {
            showToast("El registro de asistencias aún no inicia", "info");
          } catch (e) {}
          return;
        }
        // Require that lookup found the student (local or external). We do
        // not accept manual creation via this flow.
        if (!this.walkin.control_number) {
          try {
            showToast("Ingrese número de control", "info");
          } catch (e) {
            alert("Ingrese número de control");
          }
          return;
        }
        if (this.walkinLookupState !== "found") {
          try {
            showToast("Primero busque y seleccione el estudiante", "info");
          } catch (e) {
            alert("Primero busque y seleccione el estudiante");
          }
          return;
        }
        const payload = {
          token: this.token,
          control_number: this.walkin.control_number,
        };
        const resp = await fetch("/api/public/registrations/walkin", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const json = await resp.json().catch(() => ({}));
        if (resp.ok || resp.status === 201) {
          this.fetchRegs();
          this.closeWalkin();
          try {
            showToast("Walk-in registrado", "success");
          } catch (e) {
            alert("Walk-in registrado");
          }
        } else {
          try {
            showToast(json.message || "Error", "error");
          } catch (e) {
            alert(json.message || "Error");
          }
        }
      } catch (e) {
        console.error("walkin error", e);
      }
    },
  };
}

window.registrationsPublic = registrationsPublic;
