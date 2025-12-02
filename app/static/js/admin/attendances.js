// attendances.js - Alpine component for admin quick-register
// Exports window.attendancesAdmin

// Top-level helper to dispatch a standardized `attendance:changed` event.
function dispatchAttendanceChangedEvent(detail) {
  try {
    if (typeof window === "undefined") return;
    try {
      window.dispatchEvent(new CustomEvent("attendance:changed", { detail }));
    } catch (e) {
      try {
        window.dispatchEvent(new Event("attendance:changed"));
      } catch (_) {
        // swallow - non-DOM or restricted env
      }
    }
  } catch (e) {
    // ignore
  }
}

function attendancesAdmin() {
  return {
    // State
    events: [],
    activities: [],
    activityTypes: [],
    attendances: [],
    // Global stats returned by the server for the whole query
    globalStats: null,
    // Pagination
    page: 1,
    per_page: 10,
    total: 0,
    pages: 1,
    loading: false,
    filters: {
      search: "",
      activity_id: "",
      event_id: "",
      // estado de filtro: 'all' | 'walkins' | 'registered'
      status_filter: "all",
      activity_type: "",
    },

    // CSV download removed as per UX request

    // Stats for dashboard cards
    statsToday: 0,
    statsWalkins: 0,
    statsConverted: 0,
    statsErrors: 0,

    // Modal state
    showModal: false,
    modalStudentId: "",
    modalActivityId: "",
    modalMarkPresent: false,
    // Walk-in register helpers
    selectedEventForRegister: "",
    selectedActivity: "",
    selectedStudent: null,
    selectedRegistration: null,
    studentSearchQuery: "",
    studentSearchResults: [],
    // Registration view modal
    showRegistrationModal: false,
    registrationModalData: null,
    // Edit attendance modal state
    showEditAttendanceModal: false,
    // initialize as object to avoid Alpine binding errors when template renders
    editAttendanceData: {},
    editSubmitting: false,
    // Sync modal state
    showSyncModal: false,
    syncDryRun: true,
    syncSourceActivityId: null,
    syncResult: null,
    // actividades cargadas específicamente para el modal de sincronización
    modalRelatedActivities: [],
    modalRelatedLoading: false,
    // Batch checkout modal state
    showBatchCheckoutModal: false,
    batchDryRun: true,
    batchActivityId: null,
    batchEventId: null,
    batchResult: null,
    // Batch upload modal state
    showBatchUploadModal: false,
    batchUploadEventId: "",
    batchUploadDepartment: "",
    batchUploadActivityId: null,
    batchUploadFile: null,
    batchUploadDryRun: true,
    batchUploadReport: null,
    batchUploadError: null,
    batchUploadUploading: false,
    batchUploadProgress: 0,
    batchUploadView: "file",
    // UI helpers
    selectAllForSync: false,
    syncRunning: false,
    // Internal helpers to reduce duplication
    sf(url, opts) {
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      return f(url, opts);
    },

    parseAttendancesPayload(payload) {
      if (!payload) return [];
      if (Array.isArray(payload)) return payload;
      return payload.attendances || payload.data || [];
    },

    // Return activities filtered by selected event and activity_type
    filteredActivities() {
      const byEvent = this.filters.event_id
        ? this.activities.filter(
            (a) => String(a.event_id) === String(this.filters.event_id),
          )
        : this.activities.slice();

      if (this.filters.activity_type) {
        // activities coming from API use `activity_type` key
        return byEvent.filter(
          (a) => (a.activity_type || a.type) === this.filters.activity_type,
        );
      }
      return byEvent;
    },

    // Return only activities that have outgoing related activities (i.e. point to another activity)
    // (removed) activitiesWithRelations: modal now requests related activities from server

    // Return activities filtered specifically for the batch modal using batchEventId
    batchFilteredActivities() {
      const byEvent = this.batchEventId
        ? this.activities.filter(
            (a) => String(a.event_id) === String(this.batchEventId),
          )
        : this.activities.slice();
      return byEvent;
    },

    // Return attendances filtered by search, activity and status
    attendancesTableFiltered() {
      let rows = this.attendances.slice();

      if (this.filters.activity_id) {
        rows = rows.filter(
          (r) => String(r.activity_id) === String(this.filters.activity_id),
        );
      }

      // status_filter puede ser 'all', 'walkins' (sin registro) o 'registered' (con registro)
      // Mantener compatibilidad con el antiguo flag `only_without_registration` usado en tests
      const wantsOnlyWithout =
        this.filters.status_filter === "walkins" ||
        this.filters.only_without_registration === true;
      if (wantsOnlyWithout) {
        rows = rows.filter((r) => !r.registration_id);
      } else if (this.filters.status_filter === "registered") {
        rows = rows.filter((r) => !!r.registration_id);
      }

      if (this.filters.activity_type) {
        rows = rows.filter(
          (r) => r.activity_type === this.filters.activity_type,
        );
      }

      if (this.filters.search) {
        const q = String(this.filters.search).toLowerCase();
        rows = rows.filter((r) => {
          return (
            String(r.student_name || "")
              .toLowerCase()
              .includes(q) ||
            String(r.student_identifier || "")
              .toLowerCase()
              .includes(q) ||
            String(r.activity_name || "")
              .toLowerCase()
              .includes(q)
          );
        });
      }

      // Ensure we return the original objects (no cloning) so x-model bindings
      // remain linked to the underlying attendance objects. Add a stable key
      // and initialize per-row selection state if missing.
      rows.forEach((row, index) => {
        if (!row.key) row.key = row.id || `row-${index}`;
        if (typeof row.__selected_for_sync === "undefined")
          row.__selected_for_sync = false;
      });

      return rows;
    },

    // Normalizar campos que la plantilla espera: status tokens, statusLabel, date_display, activity_type
    normalizeAttendances() {
      const statusMap = {
        Asistió: "present",
        Parcial: "registered",
        Registrado: "registered",
        Confirmado: "registered",
        Ausente: "error",
        // admitir tokens en inglés por si vienen así
        present: "present",
        registered: "registered",
        error: "error",
      };

      // Mutate attendances in-place to preserve object references used by Alpine x-model
      (this.attendances || []).forEach((a) => {
        // activity_type may be nested under a.activity.activity_type or activity_type
        if (!a.activity_type) {
          a.activity_type =
            (a.activity && (a.activity.activity_type || a.activity.type)) ||
            a.activity_type ||
            "";
        }

        // Normalize status token and label
        const rawStatus = a.status || "";
        a.status = statusMap[rawStatus] || statusMap[String(rawStatus)] || null;
        a.statusLabel =
          rawStatus ||
          (a.status === "present"
            ? "Asistió"
            : a.status === "registered"
              ? "Parcial"
              : a.status === "error"
                ? "Ausente"
                : "");

        // date_display: usar created_at si existe, formatear simple YYYY-MM-DD HH:mm
        const created = a.created_at || a.createdAt || a.date || null;
        if (created) {
          try {
            const d = new Date(created);
            if (!isNaN(d)) {
              const pad = (n) => String(n).padStart(2, "0");
              const y = d.getFullYear();
              const m = pad(d.getMonth() + 1);
              const day = pad(d.getDate());
              const hh = pad(d.getHours());
              const mm = pad(d.getMinutes());
              a.date_display = `${y}-${m}-${day} ${hh}:${mm}`;
            } else {
              a.date_display = String(created);
            }
          } catch (e) {
            a.date_display = String(created);
          }
        } else {
          a.date_display = "—";
        }
      });
    },

    calculateStats() {
      // statsToday: número de asistencias creadas hoy
      const today = new Date();
      const isSameDay = (d1, d2) =>
        d1.getFullYear() === d2.getFullYear() &&
        d1.getMonth() === d2.getMonth() &&
        d1.getDate() === d2.getDate();

      // If server provided aggregated stats for the full query, prefer them
      if (this.globalStats) {
        this.statsToday =
          this.globalStats.today || this.globalStats.stats_today || 0;
        this.statsWalkins = this.globalStats.walkins || 0;
        this.statsConverted = this.globalStats.converted || 0;
        this.statsErrors = this.globalStats.errors || 0;
        return;
      }

      this.statsToday = (this.attendances || []).filter((att) => {
        if (!att.created_at) return false;
        const d = new Date(att.created_at);
        if (isNaN(d)) return false;
        return isSameDay(d, today);
      }).length;

      // Walk-ins: sin registration_id
      this.statsWalkins = (this.attendances || []).filter(
        (att) => !att.registration_id,
      ).length;

      // Converted: con registration_id y status present
      this.statsConverted = (this.attendances || []).filter(
        (att) =>
          att.registration_id &&
          (att.status === "present" || att.status === "registered"),
      ).length;

      // Errors: marcar como aquellas con status 'error' o attendance_percentage < 50
      this.statsErrors = (this.attendances || []).filter(
        (att) =>
          att.status === "error" ||
          (typeof att.attendance_percentage === "number" &&
            att.attendance_percentage < 50),
      ).length;
    },

    async init() {
      // Load basic lists used by filters
      await this.loadEvents();
      await this.loadActivities();
      // derive activityTypes from activities (API uses `activity_type`)
      this.activityTypes = Array.from(
        new Set(
          this.activities.map((a) => a.activity_type || a.type).filter(Boolean),
        ),
      );
      // initial refresh of attendances
      await this.refresh();
    },

    // Listen for dispatch to open the sync modal (from template)
    // Alpine will capture the event on the component root
    $el: null,

    async refresh() {
      this.loading = true;
      try {
        // preserve current selections so refresh() doesn't clobber user choices
        const prevSelectedIds = new Set(
          (this.attendances || [])
            .filter((r) => r.__selected_for_sync)
            .map((r) => r.id || r.student_id)
            .filter(Boolean),
        );

        // load attendances with current filters (server-side support optional)
        const qs = new URLSearchParams();
        // include pagination params so backend returns correct page
        qs.set("page", String(this.page || 1));
        qs.set("per_page", String(this.per_page || 10));
        if (this.filters.search) qs.set("search", this.filters.search);
        if (this.filters.activity_id)
          qs.set("activity_id", this.filters.activity_id);
        if (this.filters.event_id) qs.set("event_id", this.filters.event_id);
        // Solo enviar parámetro al backend para walk-ins (compatibilidad histórica)
        if (this.filters.status_filter === "walkins")
          qs.set("only_without_registration", "1");
        if (this.filters.activity_type)
          qs.set("activity_type", this.filters.activity_type);

        const url = "/api/attendances?" + qs.toString();
        const res = await this.sf(url, { method: "GET" });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));
        this.attendances = this.parseAttendancesPayload(body);

        // consume aggregated stats returned by the API for the whole query
        try {
          this.globalStats = body.stats || null;
        } catch (e) {
          this.globalStats = null;
        }

        // pagination metadata (backend returns total/pages/current_page)
        try {
          this.total = body.total || body.count || this.total || 0;
          this.pages =
            body.pages ||
            Math.max(1, Math.ceil((this.total || 0) / (this.per_page || 10)));
          this.page = body.current_page || this.page || 1;
        } catch (e) {
          // ignore if response shape unexpected
        }

        // Normalizar datos para la plantilla (status tokens, date_display, activity_type)
        this.normalizeAttendances();

        // Re-apply previous per-row selection where possible (by id or student_id)
        (this.attendances || []).forEach((a) => {
          const key = a.id || a.student_id;
          if (key && prevSelectedIds.has(key)) a.__selected_for_sync = true;
          // ensure flag exists
          if (typeof a.__selected_for_sync === "undefined")
            a.__selected_for_sync = false;
        });

        // Update master checkbox to reflect visible rows
        const visibleNow = this.attendancesTableFiltered() || [];
        this.selectAllForSync =
          visibleNow.length > 0 &&
          visibleNow.every((r) => !!r.__selected_for_sync);

        // Calcular stats después de normalizar
        this.calculateStats();
      } catch (err) {
        console.error(err);
      } finally {
        this.loading = false;
      }
    },

    // Helper to format dates with AM/PM for use in table and modal
    formatDateAMPM(dateStr) {
      if (!dateStr) return "";
      try {
        let d = new Date(dateStr);
        if (isNaN(d) && typeof dateStr === "string") {
          d = new Date(dateStr.replace(" ", "T"));
        }
        if (isNaN(d)) return String(dateStr);
        const pad = (n) => String(n).padStart(2, "0");
        let hours = d.getHours();
        const minutes = pad(d.getMinutes());
        const ampm = hours >= 12 ? "PM" : "AM";
        hours = hours % 12;
        hours = hours ? hours : 12;
        return `${pad(d.getDate())}/${pad(
          d.getMonth() + 1,
        )}/${d.getFullYear()} ${hours}:${minutes} ${ampm}`;
      } catch (e) {
        return String(dateStr);
      }
    },

    // Sync modal helpers
    async openSyncModal() {
      this.showSyncModal = true;
      this.syncDryRun = true;
      this.syncSourceActivityId = "";
      this.syncResult = null;
      // Cargar actividades relacionadas desde el servidor para el modal
      // (evita afectar selects globales y hace el filtrado en backend)
      await this.loadModalRelatedActivities();
      // Preserve existing per-row selections. Set master checkbox state based
      // on currently visible rows so UI reflects the current selection.
      const visible = this.attendancesTableFiltered() || [];
      this.selectAllForSync =
        visible.length > 0 && visible.every((r) => !!r.__selected_for_sync);
    },

    async loadModalRelatedActivities() {
      this.modalRelatedActivities = [];
      this.modalRelatedLoading = true;
      try {
        const qs = new URLSearchParams();
        qs.set("per_page", "500");
        qs.set("has_related", "1");
        // if the UI has a selected event filter, send it so backend filters by event
        if (this.filters && this.filters.event_id)
          qs.set("event_id", String(this.filters.event_id));

        const url = "/api/activities?" + qs.toString();
        const res = await this.sf(url, { method: "GET" });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));
        this.modalRelatedActivities = body.activities || body.data || [];
      } catch (e) {
        console.error("Error loading related activities for modal", e);
        this.modalRelatedActivities = [];
      } finally {
        this.modalRelatedLoading = false;
      }
    },

    closeSyncModal() {
      this.showSyncModal = false;
      this.syncResult = null;
    },

    // Batch checkout modal helpers
    openBatchCheckoutModal() {
      this.showBatchCheckoutModal = true;
      this.batchDryRun = true;
      this.batchEventId = this.filters.event_id || null;
      this.batchActivityId = this.filters.activity_id || null;
      this.batchResult = null;
    },

    closeBatchCheckoutModal() {
      this.showBatchCheckoutModal = false;
      this.batchResult = null;
    },

    async performBatchCheckout() {
      this.batchResult = null;
      if (!this.batchEventId) {
        window.showToast &&
          window.showToast(
            "Selecciona un evento antes de elegir la actividad",
            "error",
          );
        return;
      }
      if (!this.batchActivityId) {
        window.showToast &&
          window.showToast("Selecciona una actividad válida", "error");
        return;
      }
      try {
        const payload = {
          activity_id: this.batchActivityId,
          dry_run: !!this.batchDryRun,
        };
        const res = await this.sf("/api/attendances/batch-checkout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));
        this.batchResult = body.summary || body;
        if (!this.batchDryRun && res && res.ok) {
          window.showToast &&
            window.showToast("Batch checkout realizado", "success");
          await this.refresh();
          this.closeBatchCheckoutModal();
        } else if (this.batchDryRun) {
          window.showToast &&
            window.showToast("Previsualización completada (dry-run)", "info");
        }
      } catch (e) {
        console.error(e);
        window.showToast &&
          window.showToast("Error al ejecutar batch checkout", "error");
      }
    },

    async performSync() {
      // clear previous result so UI shows fresh state when starting
      this.syncResult = null;
      // Validar activity id
      if (!this.syncSourceActivityId) {
        window.showToast &&
          window.showToast(
            "Selecciona una actividad a sincronizar válida",
            "error",
          );
        return;
      }
      const activityExists = (this.activities || []).some(
        (a) => String(a.id) === String(this.syncSourceActivityId),
      );
      if (!activityExists) {
        window.showToast &&
          window.showToast("La actividad seleccionada no existe", "error");
        return;
      }

      this.syncRunning = true;
      try {
        // Gather selected rows from this.attendances
        // gather selected rows FROM the currently visible/filtered set
        const visible = this.attendancesTableFiltered();
        const selected = (visible || []).filter((r) => r.__selected_for_sync);
        const student_ids = selected.length
          ? selected.map((r) => r.student_id)
          : null;
        console.debug("performSync payload", {
          source_activity_id: this.syncSourceActivityId,
          student_ids,
          dry_run: !!this.syncDryRun,
        });
        const payload = {
          source_activity_id: this.syncSourceActivityId,
          student_ids: student_ids,
          dry_run: !!this.syncDryRun,
        };

        const res = await this.sf("/api/attendances/sync-related", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));
        // Keep full response and merge metadata into syncResult so template can access resolved_source
        const full = body || {};
        this.syncResult = full.summary || full;
        if (full.resolved_source)
          this.syncResult.resolved_source = full.resolved_source;
        if (full.selected_activity)
          this.syncResult.selected_activity = full.selected_activity;

        // Enriquecer detalles con nombres cuando sea posible (backend también los incluye cuando puede)
        try {
          (this.syncResult.details || []).forEach((d) => {
            // target_activity_name is provided by backend; no client-side enrichment required
            // Prefer backend-provided student fields; fallback to current attendances cache (best-effort)
            const cached = (this.attendances || []).find(
              (x) => String(x.student_id) === String(d.student_id),
            );
            if (!d.student_name && cached) {
              d.student_name =
                cached.student_name || cached.student_identifier || "";
            }
            // Prefer server student_identifier; fallback to cache.control_number
            d.student_identifier =
              d.student_identifier ||
              (cached &&
                (cached.student_identifier || cached.control_number)) ||
              "";
          });
        } catch (e) {
          // ignore enrichment errors
        }

        if (!this.syncDryRun && res && res.ok) {
          window.showToast &&
            window.showToast("Sincronización realizada", "success");
          // refresh to show newly created attendances
          await this.refresh();
          // limpiar selección
          (this.attendances || []).forEach(
            (r) => (r.__selected_for_sync = false),
          );
          this.selectAllForSync = false;
          // cerrar modal
          this.closeSyncModal();
        } else if (this.syncDryRun) {
          window.showToast &&
            window.showToast("Previsualización completada (dry-run)", "info");
        }
      } catch (e) {
        console.error(e);
        window.showToast && window.showToast("Error al sincronizar", "error");
      } finally {
        this.syncRunning = false;
      }
    },

    // Return number of selected rows within the currently visible/filtered set
    selectedForSyncCount() {
      const visible = this.attendancesTableFiltered() || [];
      return (visible || []).filter((r) => !!r.__selected_for_sync).length;
    },

    // Return number of visible rows in current filters
    visibleForSyncCount() {
      const visible = this.attendancesTableFiltered() || [];
      return visible.length;
    },

    toggleSelectAll(checked) {
      const newVal = !!checked;
      this.selectAllForSync = newVal;
      // Only toggle rows that are currently visible after filters
      const visible = this.attendancesTableFiltered() || [];
      visible.forEach((r) => (r.__selected_for_sync = newVal));
    },

    // Pagination helpers
    async changePage(newPage) {
      const n = parseInt(newPage, 10) || 1;
      if (n < 1) return;
      if (this.pages && n > this.pages) return;
      this.page = n;
      await this.refresh();
    },

    async setPerPage(n) {
      const p = parseInt(n, 10) || 10;
      this.per_page = p;
      this.page = 1;
      await this.refresh();
    },

    async loadEvents() {
      try {
        const res = await this.sf("/api/events?per_page=100", {
          method: "GET",
        });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));
        // Mostrar solo eventos activos en los selectores para evitar listas largas
        const allEvents = body.data || body.events || [];
        this.events = (allEvents || []).filter(
          (e) =>
            e.is_active === true || e.is_active === "true" || e.active === true,
        );
      } catch (e) {
        this.events = [];
      }
    },

    async loadActivities() {
      try {
        const res = await this.sf("/api/activities?per_page=500", {
          method: "GET",
        });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));
        this.activities = body.data || body.activities || [];
      } catch (e) {
        this.activities = [];
      }
    },

    async submitAssign() {
      if (!this.selectedActivity || !this.selectedStudent) return;
      const payload = {
        activity_id: this.selectedActivity,
        student_id: this.selectedStudent.id,
      };
      // Allow explicit mark_present from modal (modalMarkPresent) or from an
      // existingAttendance if present. Use defensive checks to avoid errors
      // when existingAttendance is undefined.
      if (
        this.modalMarkPresent ||
        (this.existingAttendance && this.existingAttendance.mark_present)
      )
        payload.mark_present = true;
      if (
        this.existingAttendance &&
        this.existingAttendance.check_in_time_input
      )
        payload.check_in_time = this.existingAttendance.check_in_time_input;
      if (
        this.existingAttendance &&
        this.existingAttendance.check_out_time_input
      )
        payload.check_out_time = this.existingAttendance.check_out_time_input;

      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f("/api/attendances/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          const assignedDefault = "Asistencia asignada correctamente.";
          const bodyMsg =
            body && typeof body.message === "string" ? body.message : "";
          const finalMessage =
            bodyMsg && bodyMsg !== "ok" ? bodyMsg : assignedDefault;

          if (res.status === 201) {
            window.showToast(
              body.message || "Asistencia creada correctamente.",
              "success",
            );
          } else if (res.status === 200) {
            window.showToast(
              body.message || "Asistencia actualizada correctamente.",
              "success",
            );
          } else {
            window.showToast(
              body.message || "Operaci\u00f3n completada.",
              "info",
            );
          }

          const dispatchedStudentId = this.selectedStudent?.id;
          this.message = finalMessage;
          this.selectedStudent = null;
          // call loadExistingAttendance if available (some builds may expose it)
          if (typeof this.loadExistingAttendance === "function") {
            await this.loadExistingAttendance();
          }
          // refresh attendances list to show the new/updated record
          if (typeof this.refresh === "function") await this.refresh();

          // Notify other modules about the attendance change
          this.dispatchAttendanceChanged({
            activity_id: this.selectedActivity,
            student_id: dispatchedStudentId,
          });
          // close the modal after success
          this.closeModal();
        } else {
          window.showToast(
            body.message || "Error al asignar asistencia.",
            "error",
          );
        }
      } catch (err) {
        console.error(err);
        window.showToast(
          "Error de conexi\u00f3n al asignar asistencia.",
          "error",
        );
      }
    },

    // Modal methods
    openRegister() {
      // Open the richer register modal (walk-in): reset selection state
      this.showModal = true;
      // fuerza selección vacía para obligar a elegir un evento
      this.selectedEventForRegister = "";
      this.selectedActivity = "";
      this.selectedStudent = null;
      this.studentSearchQuery = "";
      this.studentSearchResults = [];
      // Por defecto marcar walk-ins como presentes para evitar creaciones como 'Ausente'
      this.modalMarkPresent = true;
    },

    async searchStudents(q) {
      if (!q || String(q).trim().length === 0) {
        this.studentSearchResults = [];
        return;
      }
      try {
        const params = new URLSearchParams();
        params.set("per_page", 10);
        params.set("search", q);
        const res = await this.sf(`/api/students?${params.toString()}`, {
          method: "GET",
        });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));
        // API returns { students: [...] } or array - normalize
        this.studentSearchResults = body.students || body || [];
      } catch (e) {
        console.error(e);
        this.studentSearchResults = [];
      }
    },

    // debounce helper: call this on input with Alpine's .debounce or directly
    doStudentSearch() {
      const q = String(this.studentSearchQuery || "").trim();
      if (q.length === 0) {
        this.studentSearchResults = [];
        return;
      }
      // Trigger search
      this.searchStudents(q);
    },

    async checkExistingRegistration() {
      // If we have both student and activity, query registrations to see if one exists
      this.selectedRegistration = null;
      const studentId = this.selectedStudent && this.selectedStudent.id;
      const activityId = this.selectedActivity;
      if (!studentId || !activityId) return;
      try {
        const params = new URLSearchParams();
        params.set("student_id", studentId);
        params.set("activity_id", activityId);
        params.set("per_page", 1);
        const res = await this.sf(`/api/registrations?${params.toString()}`, {
          method: "GET",
        });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));
        const regs = body.registrations || body.data || [];
        if (Array.isArray(regs) && regs.length > 0) {
          this.selectedRegistration = regs[0];
        } else {
          this.selectedRegistration = null;
        }
      } catch (e) {
        console.error("Error checking registration", e);
        this.selectedRegistration = null;
      }
    },

    // TEMP: stubbed out flattenRegistrationData for debugging modal rendering
    // The original implementation was removed temporarily. Do NOT reintroduce
    // network calls while debugging the static modal layout.
    flattenRegistrationData(src) {
      // return null to indicate flattening is intentionally disabled
      return null;
    },

    closeModal() {
      this.showModal = false;
      // Reset modal-specific state to avoid stale data when reopened
      this.selectedRegistration = null;
      this.selectedStudent = null;
      this.studentSearchResults = [];
      this.studentSearchQuery = "";
      this.modalMarkPresent = false;
    },

    async openRegistrationModal(row) {
      // Restore real behavior: fetch synthesized (flat) registration data
      // from the backend using the optional synth flag we added.
      console.debug("openRegistrationModal called", row);
      this.registrationModalData = null;
      this.showRegistrationModal = false;

      // Determine registration id from input: accept either a registration
      // object, an attendance row with registration_id, or a plain id.
      let registrationId = null;
      if (!row) {
        window.showToast &&
          window.showToast("No hay registro especificado", "error");
        return;
      }

      // If row is a number, treat as id
      if (typeof row === "number") registrationId = row;

      // If row looks like an object with id or registration_id
      if (!registrationId && typeof row === "object") {
        if (row.registration_id) registrationId = row.registration_id;
        else if (row.id && row.activity_id && row.student_id)
          registrationId = row.id;
        else if (row.id) registrationId = row.id;
      }

      if (!registrationId) {
        window.showToast &&
          window.showToast("No se pudo determinar el ID del registro", "error");
        return;
      }

      try {
        const url = `/api/registrations/${registrationId}?synth=1`;
        const res = await this.sf(url, { method: "GET" });
        const body = await (res && res.json
          ? res.json().catch(() => ({}))
          : Promise.resolve({}));

        // Prefer the synthesized flat object, fallback to nested registration
        const synth = body.synthesized || body.registration || null;
        if (!synth) {
          window.showToast &&
            window.showToast(
              "No hay información de registro disponible",
              "warning",
            );
          this.registrationModalData = null;
          this.showRegistrationModal = true; // still show modal so user sees fallback
          return;
        }

        // Normalize to expected flat keys if necessary (some callers expect specific names)
        const data = {
          id:
            synth.registration_id || synth.id || synth.registration?.id || null,
          registration_id: synth.registration_id || synth.id || null,
          student_id: synth.student_id || (synth.student || {}).id || null,
          student_name:
            synth.student_name || (synth.student || {}).full_name || null,
          student_identifier:
            synth.student_identifier ||
            (synth.student || {}).control_number ||
            null,
          email: synth.email || (synth.student || {}).email || null,
          activity_id: synth.activity_id || (synth.activity || {}).id || null,
          activity_name:
            synth.activity_name || (synth.activity || {}).name || null,
          event_name:
            synth.event_name ||
            ((synth.activity || {}).event || {}).name ||
            null,
          status: synth.status || (synth.registration || {}).status || null,
          registration_date:
            synth.registration_date || synth.created_at || null,
          confirmation_date:
            synth.confirmation_date ||
            (synth.registration && synth.registration.confirmation_date) ||
            (body.registration && body.registration.confirmation_date) ||
            null,
          __raw: body.registration || null,
        };

        this.registrationModalData = data;
        this.showRegistrationModal = true;
      } catch (e) {
        console.error("Error loading registration", e);
        window.showToast &&
          window.showToast("Error al cargar información de registro", "error");
        this.registrationModalData = null;
        this.showRegistrationModal = true;
      }
    },

    goToRegistration(row) {
      // Open in-modal view when possible (uses the stubbed openRegistrationModal)
      this.openRegistrationModal(row);
    },

    // Open editor for an attendance row.
    // Opens a dedicated edit modal (showEditAttendanceModal) prefilled with
    // attendance data. If the row has an associated registration the modal
    // still opens and shows a link to view the registration.
    openEditor(row) {
      try {
        if (!row) return;

        // Build a normalized edit object with safe defaults
        const edit = {
          id: row.id || null,
          attendance_id: row.id || null,
          student_id: row.student_id || (row.student && row.student.id) || null,
          student_name:
            row.student_name || (row.student && row.student.full_name) || "",
          student_identifier:
            row.student_identifier ||
            (row.student && row.student.control_number) ||
            "",
          activity_id: row.activity_id || null,
          activity_name:
            row.activity_name || (row.activity && row.activity.name) || "",
          event_name:
            row.event_name ||
            (row.activity && row.activity.event && row.activity.event.name) ||
            "",
          registration_id: row.registration_id || null,
          check_in_time: row.check_in_time || row.check_in_time_input || null,
          check_out_time:
            row.check_out_time || row.check_out_time_input || null,
          mark_present: !!(
            row.status === "present" ||
            row.status === "Asistió" ||
            row.mark_present
          ),
          notes: row.notes || "",
        };

        this.editAttendanceData = edit;
        this.showEditAttendanceModal = true;
      } catch (e) {
        console.error("openEditor error", e);
      }
    },

    closeEditModal() {
      this.showEditAttendanceModal = false;
      // keep as an empty object so bindings don't throw when modal hidden/shown
      this.editAttendanceData = {};
      this.editSubmitting = false;
    },

    async submitEdit() {
      // Basic validation: need an attendance id and the underlying student/activity
      if (!this.editAttendanceData || !this.editAttendanceData.id) {
        window.showToast && window.showToast("Registro no válido", "error");
        return;
      }

      if (
        !this.editAttendanceData.student_id ||
        !this.editAttendanceData.activity_id
      ) {
        window.showToast &&
          window.showToast(
            "Faltan student_id o activity_id necesarios para guardar",
            "error",
          );
        return;
      }

      this.editSubmitting = true;
      try {
        // Build payload expected by /api/attendances/register
        const payload = {
          student_id: this.editAttendanceData.student_id,
          activity_id: this.editAttendanceData.activity_id,
        };

        if (this.editAttendanceData.check_in_time)
          payload.check_in_time = this.editAttendanceData.check_in_time;
        if (this.editAttendanceData.check_out_time)
          payload.check_out_time = this.editAttendanceData.check_out_time;
        if (typeof this.editAttendanceData.mark_present !== "undefined")
          payload.mark_present = !!this.editAttendanceData.mark_present;
        if (this.editAttendanceData.notes)
          payload.notes = this.editAttendanceData.notes;

        // The backend does not expose PATCH for attendances; use the register
        // endpoint which accepts student_id + activity_id and will create or
        // update the existing attendance as appropriate.
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const res = await f("/api/attendances/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const body = res && res.json ? await res.json().catch(() => ({})) : {};
        if (res && res.ok) {
          const msg =
            body.message ||
            (res.status === 201
              ? "Asistencia creada"
              : "Asistencia actualizada");
          window.showToast && window.showToast(msg, "success");
          await this.refresh();
          this.closeEditModal();
          this.dispatchAttendanceChanged({
            attendance_id: this.editAttendanceData.id,
            activity_id: this.editAttendanceData.activity_id,
            student_id: this.editAttendanceData.student_id,
          });
        } else {
          window.showToast &&
            window.showToast(
              body.message || "Error al actualizar asistencia",
              "error",
            );
        }
      } catch (e) {
        console.error("submitEdit error", e);
        window.showToast &&
          window.showToast(
            "Error de conexión al actualizar asistencia",
            "error",
          );
      } finally {
        this.editSubmitting = false;
      }
    },

    closeRegistrationModal() {
      this.showRegistrationModal = false;
      this.registrationModalData = null;
    },

    async deleteAttendance(row) {
      if (!confirm("¿Estás seguro de eliminar esta asistencia?")) return;

      try {
        const res = await this.sf(`/api/attendances/${row.id}`, {
          method: "DELETE",
        });

        if (res.ok) {
          window.showToast &&
            window.showToast("Asistencia eliminada", "success");
          await this.refresh();

          this.dispatchAttendanceChanged({
            attendance_id: row.id,
            activity_id: row.activity_id,
            student_id: row.student_id,
          });
        } else {
          const body = await res.json().catch(() => ({}));
          window.showToast &&
            window.showToast(
              body.message || "Error al eliminar asistencia",
              "error",
            );
        }
      } catch (err) {
        console.error(err);
        window.showToast && window.showToast("Error de conexión", "error");
      }
    },

    async pauseAttendance(row) {
      if (
        !confirm(
          "¿Pausar esta asistencia? Esto detiene el conteo de tiempo presente.",
        )
      )
        return;

      try {
        const res = await this.sf(`/api/attendances/pause`, {
          method: "POST",
          body: JSON.stringify({
            student_id: row.student_id,
            activity_id: row.activity_id,
          }),
        });

        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          window.showToast &&
            window.showToast(body.message || "Asistencia pausada", "success");
          await this.refresh();

          this.dispatchAttendanceChanged({
            attendance_id: row.id,
            activity_id: row.activity_id,
            student_id: row.student_id,
          });
        } else {
          window.showToast &&
            window.showToast(
              body.message || "Error al pausar asistencia",
              "error",
            );
        }
      } catch (err) {
        console.error(err);
        window.showToast && window.showToast("Error de conexión", "error");
      }
    },

    async resumeAttendance(row) {
      if (
        !confirm(
          "¿Reanudar esta asistencia? Esto continúa el conteo de tiempo presente.",
        )
      )
        return;

      try {
        const res = await this.sf(`/api/attendances/resume`, {
          method: "POST",
          body: JSON.stringify({
            student_id: row.student_id,
            activity_id: row.activity_id,
          }),
        });

        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          window.showToast &&
            window.showToast(body.message || "Asistencia reanudada", "success");
          await this.refresh();

          this.dispatchAttendanceChanged({
            attendance_id: row.id,
            activity_id: row.activity_id,
            student_id: row.student_id,
          });
        } else {
          window.showToast &&
            window.showToast(
              body.message || "Error al reanudar asistencia",
              "error",
            );
        }
      } catch (err) {
        console.error(err);
        window.showToast && window.showToast("Error de conexión", "error");
      }
    },

    // Batch upload modal handlers
    openBatchUploadModal() {
      this.batchUploadEventId = this.filters.event_id || "";
      this.batchUploadDepartment = "";
      this.batchUploadActivityId = null;
      this.batchUploadFile = null;
      this.batchUploadDryRun = true;
      this.batchUploadReport = null;
      this.batchUploadError = null;
      this.batchUploadProgress = 0;
      this.batchUploadView = "file";
      this.showBatchUploadModal = true;
    },

    closeBatchUploadModal() {
      this.showBatchUploadModal = false;
      this.batchUploadUploading = false;
      this.batchUploadFile = null;
      this.batchUploadReport = null;
      this.batchUploadError = null;
      this.batchUploadProgress = 0;
    },

    onBatchUploadFileChange(e) {
      const f = e && e.target && e.target.files ? e.target.files[0] : null;
      this.batchUploadFile = f;
      this.batchUploadError = null;
    },

    batchUploadFilteredDepartments() {
      if (!this.batchUploadEventId) return [];
      const eventActivities = this.activities.filter(
        (a) => String(a.event_id) === String(this.batchUploadEventId),
      );
      const depts = new Set(
        eventActivities.map((a) => a.department).filter(Boolean),
      );
      return Array.from(depts).sort();
    },

    batchUploadFilteredActivities() {
      if (!this.batchUploadEventId || !this.batchUploadDepartment) return [];
      return this.activities.filter(
        (a) =>
          String(a.event_id) === String(this.batchUploadEventId) &&
          a.department === this.batchUploadDepartment,
      );
    },

    async submitBatchUpload() {
      if (!this.batchUploadActivityId) {
        this.batchUploadError = "Seleccione una actividad para la carga";
        return;
      }
      if (!this.batchUploadFile) {
        this.batchUploadError = "Seleccione un archivo TXT o XLSX";
        return;
      }

      this.batchUploadUploading = true;
      this.batchUploadReport = null;
      this.batchUploadError = null;
      this.batchUploadProgress = 0;

      try {
        const fd = new FormData();
        fd.append("file", this.batchUploadFile);
        fd.append("activity_id", String(this.batchUploadActivityId));
        fd.append("dry_run", this.batchUploadDryRun ? "1" : "0");

        await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open("POST", "/api/attendances/batch", true);
          // Inject Authorization header if token is present
          try {
            const token =
              typeof window.getAuthToken === "function"
                ? window.getAuthToken()
                : localStorage.getItem("authToken");
            if (token) {
              xhr.setRequestHeader("Authorization", `Bearer ${token}`);
            }
          } catch (e) {
            // ignore
          }

          xhr.upload.onprogress = (ev) => {
            if (ev.lengthComputable) {
              this.batchUploadProgress = Math.round(
                (ev.loaded / ev.total) * 100,
              );
            }
          };

          xhr.onload = () => {
            this.batchUploadUploading = false;
            if (xhr.status >= 200 && xhr.status < 300) {
              try {
                const report = JSON.parse(xhr.responseText || "{}");
                this.batchUploadReport = report.report || report || {};
                // Normalize shape so templates can iterate safely
                this.batchUploadReport.details =
                  this.batchUploadReport.details || [];
                this.batchUploadReport.errors =
                  this.batchUploadReport.errors || [];
                // Prefer server-provided dry_run flag when available; fallback to top-level report or client value
                try {
                  const serverDry =
                    report &&
                    (report.report &&
                    typeof report.report.dry_run !== "undefined"
                      ? report.report.dry_run
                      : typeof report.dry_run !== "undefined"
                        ? report.dry_run
                        : undefined);
                  this.batchUploadReport.dry_run =
                    typeof serverDry !== "undefined"
                      ? !!serverDry
                      : !!this.batchUploadDryRun;
                } catch (e) {
                  this.batchUploadReport.dry_run = !!this.batchUploadDryRun;
                }
                this.batchUploadReport.created =
                  typeof this.batchUploadReport.created === "number"
                    ? this.batchUploadReport.created
                    : 0;
                this.batchUploadReport.skipped =
                  typeof this.batchUploadReport.skipped === "number"
                    ? this.batchUploadReport.skipped
                    : 0;
                this.batchUploadReport.not_found =
                  typeof this.batchUploadReport.not_found === "number"
                    ? this.batchUploadReport.not_found
                    : 0;
                this.batchUploadReport.invalid =
                  typeof this.batchUploadReport.invalid === "number"
                    ? this.batchUploadReport.invalid
                    : 0;
                this.batchUploadView = "report";
                // If this was not a dry run and attendances were created, reload list
                if (
                  !this.batchUploadDryRun &&
                  this.batchUploadReport &&
                  this.batchUploadReport.created &&
                  this.batchUploadReport.created > 0
                ) {
                  this.refresh();
                }
                window.showToast &&
                  window.showToast("Importación procesada", "success");
                resolve();
              } catch (e) {
                reject(new Error("Respuesta inválida del servidor"));
              }
            } else {
              try {
                const err = JSON.parse(xhr.responseText || "{}");
                reject(new Error(err.message || JSON.stringify(err)));
              } catch (e) {
                reject(new Error(`Error ${xhr.status}`));
              }
            }
          };

          xhr.onerror = () =>
            reject(new Error("Error de red durante la subida"));

          xhr.send(fd);
        });
      } catch (err) {
        this.batchUploadUploading = false;
        this.batchUploadError = err.message || String(err);
        window.showToast && window.showToast("Error al subir archivo", "error");
      }
    },

    // Helper to add dispatch method for backward compatibility
    dispatchAttendanceChanged(detail) {
      dispatchAttendanceChangedEvent(detail);
    },
  };
}

try {
  if (typeof window !== "undefined") window.attendancesAdmin = attendancesAdmin;
} catch (e) {}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { attendancesAdmin };
  try {
    module.exports.default = module.exports;
  } catch (e) {}
}
