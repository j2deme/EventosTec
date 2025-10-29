// app/static/js/admin/activities.js
function activitiesManager() {
  return {
    // Estado
    activities: [],
    activityRelations: [],
    events: [], // Para el selector de eventos
    loading: false,
    saving: false,
    deleting: false,
    errorMessage: "",
    dateValidationError: "",
    minDate: "",
    maxDate: "",
    calculatedDuration: 0,

    // Paginación
    pagination: {
      current_page: 1,
      last_page: 1,
      total: 0,
      from: 0,
      to: 0,
      pages: [],
    },

    // Filtros
    filters: {
      search: "",
      event_id: "",
      activity_type: "",
      sort: "created_at:desc",
    },

    // Modal
    showModal: false,
    // Ver actividad (modal de lectura con token)
    showViewModal: false,
    activityToView: null,
    // Token modal state
    tokenUrl: "",
    token: "",
    // Public (chief) token state
    tokenUrlPublic: "",
    tokenPublic: "",
    tokenLoading: false,
    tokenError: "",
    // Batch import modal
    showBatchModal: false,
    batchUploading: false,
    batchFile: null,
    batchEventId: "",
    batchDryRun: true,
    batchError: null,
    batchReport: null,
    batchProgress: 0,
    // Panel lateral (nueva subvista inline) - mantener compatibilidad
    showPanel: false,
    showDeleteModal: false,
    editingActivity: null,
    // Flags para manejo de public_slug
    slugChangePrompt: false,
    _lastKnownSlug: null,
    _applyGeneratedSlugFlag: false,
    currentActivity: {
      id: null,
      event_id: "",
      department: "",
      // valor público editable por el admin
      public_slug: "",
      name: "",
      description: "",
      start_datetime: "",
      end_datetime: "",
      duration_hours: null,
      activity_type: "",
      location: "",
      modality: "",
      requirements: "",
      // nuevos campos
      knowledge_area: "",
      // Speakers as an array of objects: [{ name, degree, organization }, ...]
      speakersList: [],
      // Target audience: general flag + careers array
      target_audience_general: false,
      target_audience_careersList: [],
      max_capacity: null,
    },
    activityToDelete: null,

    // Inicialización
    init() {
      // Debug: indicar que el manager se inicializó
      // initialization
      this.loadEvents();
      this.loadActivities();
      this.loadActivityRelations();
      // Escuchar eventos de guardado/creación/actualización para mantener lista sincronizada
      try {
        window.addEventListener("activity-saved", (e) => {
          const detail = e && e.detail ? e.detail : {};
          // Si la actividad guardada es la misma que la que está abierta, recargarla
          if (
            detail.id &&
            this.currentActivity &&
            String(detail.id) === String(this.currentActivity.id)
          ) {
            this.reloadCurrentActivity();
          }
          // En cualquier caso, recargar la lista visible
          this.loadActivities(this.pagination.current_page || 1);
        });

        window.addEventListener("activity-created", (e) => {
          this.loadActivities(1);
        });

        window.addEventListener("activity-updated", (e) => {
          const detail = e && e.detail ? e.detail : {};
          if (
            detail.id &&
            this.currentActivity &&
            String(detail.id) === String(this.currentActivity.id)
          ) {
            this.reloadCurrentActivity();
          }
          this.loadActivities(this.pagination.current_page || 1);
        });
      } catch (err) {
        // ambiente sin DOM (tests)
      }
    },

    // Cargar actividades
    async loadActivities(page = 1) {
      this.loading = true;
      this.errorMessage = "";

      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;

        const params = new URLSearchParams({ page: page, per_page: 10 });
        if (this.filters.search) params.set("search", this.filters.search);
        if (this.filters.event_id)
          params.set("event_id", this.filters.event_id);
        if (this.filters.activity_type)
          params.set("activity_type", this.filters.activity_type);
        if (this.filters.sort) params.set("sort", this.filters.sort);

        const url = `/api/activities?${params.toString()}`;
        const response = await f(url);
        if (!response || !response.ok)
          throw new Error(
            `Error al cargar actividades: ${response && response.status}`
          );

        const data = await response.json();

        this.activities = (data.activities || []).map((activity) => {
          const act = {
            ...activity,
            start_datetime: this.formatDateTimeForInput(
              activity.start_datetime
            ),
            end_datetime: this.formatDateTimeForInput(activity.end_datetime),
          };
          // Compute a compact speakersString for display in the table.
          try {
            const speakers = Array.isArray(activity.speakers)
              ? activity.speakers
              : [];
            act.speakersString = speakers
              .map((s) => {
                if (!s) return "";
                const name = (s.name || "").trim();
                const degree = (s.degree || "").trim();
                if (degree) {
                  // Mostrar grado primero seguido del nombre
                  return `${degree} ${name}`.trim();
                }
                return name;
              })
              .filter(Boolean)
              .join(", ");
          } catch (e) {
            act.speakersString = "";
          }
          // Compute a human-friendly dates string with AM/PM using dayjs
          // - Single-day: DD/MM/YY h:mm A - h:mm A
          try {
            const hasDayjs = typeof dayjs !== "undefined";
            if (hasDayjs && typeof dayjs.locale === "function")
              dayjs.locale("es");

            const s = activity.start_datetime
              ? dayjs(activity.start_datetime)
              : null;
            const e = activity.end_datetime
              ? dayjs(activity.end_datetime)
              : null;

            if (hasDayjs && s && s.isValid() && e && e.isValid()) {
              const sameDay = s.isSame(e, "day");
              if (sameDay) {
                act.datesString = `${s.format("DD/MM/YY")} ${s.format(
                  "h:mm A"
                )} - ${e.format("h:mm A")}`;
              } else {
                // Mostrar rango de días y mes abreviado en español (MMM)
                act.datesString = `${s.format("D")} - ${e.format(
                  "D"
                )} / ${s.format("MMM/YY")} ${s.format("h:mm A")} - ${e.format(
                  "h:mm A"
                )}`;
              }
            } else if (hasDayjs && s && s.isValid()) {
              act.datesString = `${s.format("DD/MM/YY")} ${s.format("h:mm A")}`;
            } else if (!hasDayjs) {
              // Fallback a la implementación previa si dayjs no está disponible
              const sd = activity.start_datetime
                ? new Date(activity.start_datetime)
                : null;
              const ed = activity.end_datetime
                ? new Date(activity.end_datetime)
                : null;
              const pad = (n) => String(n).padStart(2, "0");
              const day = (d) => pad(d.getDate());
              const month = (d) => pad(d.getMonth() + 1);
              const year2 = (d) => String(d.getFullYear()).slice(-2);
              const time12 = (d) =>
                d
                  .toLocaleTimeString("en-US", {
                    hour: "2-digit",
                    minute: "2-digit",
                    hour12: true,
                  })
                  .replace(/\u200E/g, "");

              if (sd && !isNaN(sd) && ed && !isNaN(ed)) {
                const sameDay =
                  sd.getFullYear() === ed.getFullYear() &&
                  sd.getMonth() === ed.getMonth() &&
                  sd.getDate() === ed.getDate();
                if (sameDay) {
                  act.datesString = `${day(sd)}/${month(sd)}/${year2(
                    sd
                  )} ${time12(sd)} - ${time12(ed)}`;
                } else {
                  act.datesString = `${day(sd)} - ${day(ed)} / ${month(
                    sd
                  )}/${year2(sd)} ${time12(sd)} - ${time12(ed)}`;
                }
              } else if (sd && !isNaN(sd)) {
                act.datesString = `${day(sd)}/${month(sd)}/${year2(
                  sd
                )} ${time12(sd)}`;
              } else {
                act.datesString = "Sin fecha";
              }
            } else {
              act.datesString = "Sin fecha";
            }
          } catch (err) {
            act.datesString = "Sin fecha";
          }
          return act;
        });
        // removed debug inspection block

        const pages = data.pages || 1;
        const current = data.current_page || 1;
        const total = data.total || 0;

        this.pagination = {
          current_page: current,
          last_page: pages,
          total: total,
          from: (current - 1) * 10 + 1,
          to: Math.min(current * 10, total),
          pages: Array.from({ length: pages }, (_, i) => i + 1),
        };
      } catch (error) {
        console.error("Error loading activities:", error);
        showToast("Error al cargar actividades", "error");
        this.errorMessage = error.message || "Error al cargar actividades";
      } finally {
        this.loading = false;
      }
    },

    // Cargar eventos para el selector
    async loadEvents() {
      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/events/");
        if (!response || !response.ok)
          throw new Error(
            `Error al cargar eventos: ${response && response.status}`
          );
        const data = await response.json();
        this.events = Array.isArray(data) ? data : data.events || [];
      } catch (error) {
        console.error("Error loading events:", error);
        showToast("Error al cargar eventos", "error");
        this.errorMessage = error.message || "Error al cargar eventos";
      }
    },

    updateCalculatedDuration() {
      if (
        this.currentActivity.start_datetime &&
        this.currentActivity.end_datetime
      ) {
        const start = new Date(this.currentActivity.start_datetime);
        const end = new Date(this.currentActivity.end_datetime);

        if (!isNaN(start) && !isNaN(end) && start < end) {
          const diffMs = end - start;
          this.calculatedDuration = diffMs / (1000 * 60 * 60); // Convertir a horas
        } else {
          this.calculatedDuration = 0;
        }
      } else {
        this.calculatedDuration = 0;
      }
    },

    updateDateLimits() {
      this.minDate = "";
      this.maxDate = "";

      if (this.currentActivity.event_id) {
        const selectedEvent = this.events.find(
          (e) => String(e.id) === String(this.currentActivity.event_id)
        );

        if (selectedEvent) {
          // Formatear las fechas del evento para los inputs datetime-local
          this.minDate = this.formatDateTimeForInput(selectedEvent.start_date);
          this.maxDate = this.formatDateTimeForInput(selectedEvent.end_date);
        }
      }
    },

    // Crear actividad
    async createActivity() {
      this.saving = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        // Validación: event_id es obligatorio
        if (!this.currentActivity || !this.currentActivity.event_id) {
          throw new Error("Seleccione un evento antes de crear la actividad");
        }

        // Preparar datos para enviar
        const activityData = {
          event_id: parseInt(this.currentActivity.event_id),
          department: this.currentActivity.department,
          name: this.currentActivity.name,
          description: this.currentActivity.description,
          // Include public_slug if set (backend will generate if empty)
          public_slug: this.currentActivity.public_slug || null,
          start_datetime: this.currentActivity.start_datetime,
          end_datetime: this.currentActivity.end_datetime,
          ...(this.currentActivity.duration_hours !== null &&
            this.currentActivity.duration_hours !== "" && {
              duration_hours: parseFloat(this.currentActivity.duration_hours),
            }),
          activity_type: this.currentActivity.activity_type,
          location: this.currentActivity.location,
          modality: this.currentActivity.modality,
          requirements: this.currentActivity.requirements,
          knowledge_area: this.currentActivity.knowledge_area || null,
          // Send speakers as structured array
          speakers: Array.isArray(this.currentActivity.speakersList)
            ? this.currentActivity.speakersList
            : [],
          target_audience: {
            general: !!this.currentActivity.target_audience_general,
            careers: Array.isArray(
              this.currentActivity.target_audience_careersList
            )
              ? this.currentActivity.target_audience_careersList
              : [],
          },
          max_capacity: this.currentActivity.max_capacity
            ? parseInt(this.currentActivity.max_capacity)
            : null,
        };

        const validationError = this.validateActivityDates(activityData);
        if (validationError) {
          throw new Error(validationError);
        }

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f("/api/activities/", {
          method: "POST",
          body: JSON.stringify(activityData),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al crear actividad: ${response.status} ${response.statusText}`
          );
        }

        const newActivity = await response.json();

        // Cerrar modal y recargar lista
        this.closeModal();
        this.loadActivities();

        window.dispatchEvent(
          new CustomEvent("activity-created", {
            detail: {
              action: "created",
              eventId: newActivity.id,
            },
          })
        );

        showToast("Actividad creada exitosamente", "success");
      } catch (error) {
        console.error("Error creating activity:", error);
        showToast("Error al crear actividad", "error");
        this.errorMessage = error.message || "Error al crear actividad";
      } finally {
        this.saving = false;
      }
    },

    // Actualizar actividad
    async updateActivity() {
      this.saving = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        // Validación: event_id es obligatorio
        if (!this.currentActivity || !this.currentActivity.event_id) {
          throw new Error(
            "Seleccione un evento antes de actualizar la actividad"
          );
        }

        // Preparar datos para enviar
        const activityData = {
          event_id: parseInt(this.currentActivity.event_id),
          department: this.currentActivity.department,
          name: this.currentActivity.name,
          description: this.currentActivity.description,
          // always send the current public_slug value (null -> backend auto-generate)
          public_slug: this.currentActivity.public_slug || null,
          start_datetime: this.currentActivity.start_datetime,
          end_datetime: this.currentActivity.end_datetime,
          duration_hours: parseFloat(this.currentActivity.duration_hours),
          activity_type: this.currentActivity.activity_type,
          location: this.currentActivity.location,
          modality: this.currentActivity.modality,
          requirements: this.currentActivity.requirements,
          knowledge_area: this.currentActivity.knowledge_area || null,
          speakers: Array.isArray(this.currentActivity.speakersList)
            ? this.currentActivity.speakersList
            : [],
          target_audience: {
            general: !!this.currentActivity.target_audience_general,
            careers: Array.isArray(
              this.currentActivity.target_audience_careersList
            )
              ? this.currentActivity.target_audience_careersList
              : [],
          },
          max_capacity: this.currentActivity.max_capacity
            ? parseInt(this.currentActivity.max_capacity)
            : null,
        };

        const validationError = this.validateActivityDates(activityData);
        if (validationError) {
          throw new Error(validationError);
        }

        // Include apply_generated_slug flag when the editor indicated to apply server-generated slug
        if (this._applyGeneratedSlugFlag) {
          activityData.apply_generated_slug = true;
          // reset flag after attaching to payload
          this._applyGeneratedSlugFlag = false;
        }

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(`/api/activities/${this.currentActivity.id}`, {
          method: "PUT",
          body: JSON.stringify(activityData),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al actualizar actividad: ${response.status} ${response.statusText}`
          );
        }

        const updatedActivity = await response.json();

        // Cerrar modal y recargar lista
        this.closeModal();
        this.loadActivities();

        window.dispatchEvent(
          new CustomEvent("activity-updated", {
            detail: {
              action: "updated",
              eventId: updatedActivity.id,
            },
          })
        );

        showToast("Actividad actualizada exitosamente", "success");
      } catch (error) {
        console.error("Error updating activity:", error);
        showToast("Error al actualizar actividad", "error");
        this.errorMessage = error.message || "Error al actualizar actividad";
      } finally {
        this.saving = false;
      }
    },

    // Eliminar actividad
    async deleteActivity() {
      this.deleting = true;
      this.errorMessage = "";

      try {
        const token = localStorage.getItem("authToken");
        if (!token) {
          throw new Error("No se encontró el token de autenticación");
        }

        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(
          `/api/activities/${this.activityToDelete.id}`,
          { method: "DELETE" }
        );

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.message ||
              `Error al eliminar actividad: ${response.status} ${response.statusText}`
          );
        }

        deletedId = this.activityToDelete.id;

        // Cerrar modal y recargar lista
        this.showDeleteModal = false;
        this.activityToDelete = null;
        this.loadActivities();

        window.dispatchEvent(
          new CustomEvent("activity-deleted", {
            detail: {
              action: "deleted",
              eventId: deletedId,
            },
          })
        );

        showToast("Actividad eliminada exitosamente", "success");
      } catch (error) {
        console.error("Error deleting activity:", error);
        showToast("Error al eliminar actividad", "error");
        this.errorMessage = error.message || "Error al eliminar actividad";
      } finally {
        this.deleting = false;
      }
    },

    // Abrir modal para crear
    openCreateModal() {
      this.calculatedDuration = 0;
      this.editingActivity = false;
      this.currentActivity = {
        id: null,
        event_id: "",
        department: "",
        name: "",
        description: "",
        start_datetime: "",
        end_datetime: "",
        duration_hours: 1.0,
        activity_type: "",
        location: "",
        modality: "",
        requirements: "",
        knowledge_area: "",
        speakersList: [],
        target_audience_general: false,
        target_audience_careersList: [],
        max_capacity: null,
      };
      this.minDate = "";
      this.maxDate = "";
      // mantener compatibilidad con antiguos usos de showModal
      this.showModal = true;
      this.showPanel = true;
    },

    // Batch import modal handlers
    openBatchModal() {
      // preselect current filter event if any
      this.batchEventId = this.filters.event_id || "";
      this.batchFile = null;
      this.batchDryRun = true;
      this.batchReport = null;
      this.batchError = null;
      this.batchProgress = 0;
      this.showBatchModal = true;
    },

    closeBatchModal() {
      this.showBatchModal = false;
      this.batchUploading = false;
      this.batchFile = null;
      this.batchReport = null;
      this.batchError = null;
      this.batchProgress = 0;
    },

    onBatchFileChange(e) {
      const f = e && e.target && e.target.files ? e.target.files[0] : null;
      this.batchFile = f;
      this.batchError = null;
    },

    async submitBatchUpload() {
      // Use XMLHttpRequest to get upload progress events
      if (!this.batchEventId) {
        this.batchError = "Seleccione un evento para la carga";
        return;
      }
      if (!this.batchFile) {
        this.batchError = "Seleccione un archivo .xlsx";
        return;
      }

      this.batchUploading = true;
      this.batchReport = null;
      this.batchError = null;
      this.batchProgress = 0;

      try {
        const fd = new FormData();
        fd.append("file", this.batchFile);
        fd.append("event_id", String(this.batchEventId));
        fd.append("dry_run", this.batchDryRun ? "1" : "0");

        await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open("POST", "/api/activities/batch", true);
          // Inject Authorization header if token is present in localStorage
          try {
            const token =
              window.localStorage && window.localStorage.getItem
                ? window.localStorage.getItem("authToken")
                : null;
            if (token) {
              xhr.setRequestHeader("Authorization", `Bearer ${token}`);
            }
          } catch (e) {
            // ignore localStorage access errors (e.g., in some test envs)
          }

          xhr.upload.addEventListener("progress", (ev) => {
            if (ev.lengthComputable) {
              const percent = Math.round((ev.loaded / ev.total) * 100);
              this.batchProgress = percent;
            }
          });

          xhr.onreadystatechange = () => {
            if (xhr.readyState === 4) {
              if (xhr.status >= 200 && xhr.status < 300) {
                try {
                  const data = JSON.parse(xhr.responseText || "{}");
                  // Backend returns { message, report } — prefer report if present
                  const report = data.report || data;
                  this.batchReport = report;
                  // If this was not a dry run and rows were created, reload list
                  if (
                    !this.batchDryRun &&
                    report &&
                    report.created &&
                    report.created > 0
                  ) {
                    this.loadActivities(1);
                  }
                  showToast("Importación procesada", "success");
                  resolve();
                } catch (e) {
                  reject(new Error("Respuesta inválida del servidor"));
                }
              } else {
                // Try to parse JSON error from server
                try {
                  const err = JSON.parse(xhr.responseText || "{}");
                  reject(new Error(err.message || JSON.stringify(err)));
                } catch (e) {
                  reject(new Error(`Error ${xhr.status}`));
                }
              }
            }
          };

          xhr.onerror = () =>
            reject(new Error("Error de red durante la subida"));

          xhr.send(fd);
        });
      } catch (err) {
        console.error("Batch upload error", err);
        this.batchError = err.message || String(err);
        showToast("Error al procesar importación", "error");
      } finally {
        this.batchUploading = false;
        // leave batchProgress at 100 if report exists
        if (this.batchReport && this.batchProgress < 100)
          this.batchProgress = 100;
      }
    },

    // Actividades relacionadas
    relatedActivities: [],
    selectedToLink: "",
    async loadRelatedActivities(activityId) {
      try {
        this.relatedActivities = await this.getRelatedActivities(activityId);
      } catch (error) {
        this.relatedActivities = [];
      }
    },

    // Abrir modal para editar
    async openEditModal(activity) {
      this.editingActivity = true;
      // Copiar la actividad para evitar mutaciones directas
      // Mapear speakers and target_audience for modal fields
      const mapped = { ...activity };
      // Map speakers into speakersList array
      mapped.speakersList = Array.isArray(activity.speakers)
        ? activity.speakers
        : activity.speakers
        ? Array.isArray(activity.speakers)
          ? activity.speakers
          : []
        : [];

      if (activity.target_audience) {
        mapped.target_audience_general = !!activity.target_audience.general;
        mapped.target_audience_careersList = Array.isArray(
          activity.target_audience.careers
        )
          ? activity.target_audience.careers
          : [];
      } else {
        mapped.target_audience_general = false;
        mapped.target_audience_careersList = [];
      }
      mapped.knowledge_area = activity.knowledge_area || "";
      this.currentActivity = mapped;
      // inicializar tracking del slug
      this._lastKnownSlug = activity.public_slug || null;
      this.updateDateLimits();
      // abrir panel/modal (compatibilidad)
      this.showModal = true;
      this.showPanel = true;
      this.dateValidationError = "";
      this.updateCalculatedDuration();
      if (activity.id) {
        await this.loadRelatedActivities(activity.id);
      }
    },

    // Cerrar modal
    closeModal() {
      this.showModal = false;
      this.showPanel = false;
      this.editingActivity = false;
      this.currentActivity = {
        id: null,
        event_id: "",
        department: "",
        public_slug: "",
        name: "",
        description: "",
        start_datetime: "",
        end_datetime: "",
        duration_hours: 1.0,
        activity_type: "",
        location: "",
        modality: "",
        requirements: "",
        knowledge_area: "",
        speakersList: [],
        target_audience_general: false,
        target_audience_careersList: [],
        max_capacity: null,
      };
      this.dateValidationError = "";
      this.errorMessage = "";
      this.minDate = "";
      this.maxDate = "";
    },

    // Resetear el objeto currentActivity (sin cerrar panel) - usado por el botón Cancel del panel
    resetCurrentActivity() {
      this.editingActivity = false;
      this.currentActivity = {
        id: null,
        event_id: "",
        department: "",
        public_slug: "",
        name: "",
        description: "",
        start_datetime: "",
        end_datetime: "",
        duration_hours: 1.0,
        activity_type: "",
        location: "",
        modality: "",
        requirements: "",
        knowledge_area: "",
        speakersList: [],
        target_audience_general: false,
        target_audience_careersList: [],
        max_capacity: null,
      };
      this.dateValidationError = "";
      this.errorMessage = "";
      this.minDate = "";
      this.maxDate = "";
      this.calculatedDuration = 0;
    },

    // Recargar la actividad actual desde el servidor (si existe id)
    async reloadCurrentActivity() {
      if (!this.currentActivity || !this.currentActivity.id) return;
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(`/api/activities/${this.currentActivity.id}`);
        if (!response || !response.ok)
          throw new Error(
            `Error al recargar actividad: ${response && response.status}`
          );
        const data = await response.json();
        const act = data.activity || data;
        const mapped = { ...act };
        mapped.speakersList = Array.isArray(act.speakers) ? act.speakers : [];
        if (act.target_audience) {
          mapped.target_audience_general = !!act.target_audience.general;
          mapped.target_audience_careersList = Array.isArray(
            act.target_audience.careers
          )
            ? act.target_audience.careers
            : [];
        } else {
          mapped.target_audience_general = false;
          mapped.target_audience_careersList = [];
        }
        mapped.knowledge_area = act.knowledge_area || "";
        // Track last known slug to detect manual edits vs canonical changes
        try {
          this._lastKnownSlug = act.public_slug || null;
        } catch (e) {
          this._lastKnownSlug = null;
        }
        this.currentActivity = mapped;
        this.updateDateLimits();
        this.dateValidationError = "";
        this.updateCalculatedDuration();
        if (act.id) {
          await this.loadRelatedActivities(act.id);
        }
      } catch (error) {
        console.error("Error reloading activity:", error);
        showToast("Error al recargar actividad", "error");
      }
    },

    // Confirmar eliminación
    confirmDelete(activity) {
      this.activityToDelete = activity;
      this.showDeleteModal = true;
    },

    // Guardar actividad (crear o actualizar)
    saveActivity() {
      if (this.editingActivity) {
        this.updateActivity();
      } else {
        this.createActivity();
      }
    },

    // Cambiar página
    changePage(page) {
      if (page >= 1 && page <= this.pagination.last_page) {
        this.loadActivities(page);
      }
    },

    // Ver detalles de la actividad (opcional)
    viewActivity(activity) {
      // Abrir modal de vista y solicitar token
      this.activityToView = activity;
      this.showViewModal = true;
      // iniciar fetch del token en background
      this.fetchActivityToken();
    },

    async fetchActivityToken() {
      this.tokenUrl = "";
      this.token = "";
      this.tokenLoading = true;
      this.tokenError = "";
      this.tokenUrlPublic = "";
      this.tokenPublic = "";
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const headers = {};
        try {
          const t =
            window.localStorage && window.localStorage.getItem
              ? window.localStorage.getItem("authToken")
              : null;
          if (t) headers["Authorization"] = `Bearer ${t}`;
        } catch (e) {
          // ignore localStorage errors
        }
        const res = await f(`/api/activities/${this.activityToView.id}/token`, {
          headers,
        });
        if (!res.ok) {
          let msg = "Error obteniendo token";
          try {
            const j = await res.json();
            msg = j.message || msg;
          } catch (e) {
            msg = await res.text();
          }
          this.tokenError = msg;
          return;
        }
        const data = await res.json();
        this.token = data.token || "";
        this.tokenUrl =
          data.url ||
          window.location.origin + "/self-register/" + (data.token || "");
        // Also fetch public (chief) token in parallel
        try {
          const res2 = await f(
            `/api/activities/${this.activityToView.id}/public-token`,
            { headers }
          );
          if (res2 && res2.ok) {
            const d2 = await res2.json();
            this.tokenPublic = d2.token || "";
            this.tokenUrlPublic =
              d2.url ||
              window.location.origin +
                "/public/registrations/" +
                (d2.token || "");
          }
        } catch (e) {
          // ignore public token fetch errors
        }
      } catch (e) {
        this.tokenError = e && e.message ? e.message : String(e);
      } finally {
        this.tokenLoading = false;
      }
    },

    validateActivityDates(activityData) {
      this.dateValidationError = ""; // Limpiar error anterior

      // Obtener el evento seleccionado
      const selectedEvent = this.events.find(
        (e) => String(e.id) === String(activityData.event_id)
      );
      if (!selectedEvent) {
        this.dateValidationError = "Por favor seleccione un evento válido";
        return this.dateValidationError;
      }

      // Convertir fechas a objetos Date
      const activityStart = new Date(activityData.start_datetime);
      const activityEnd = new Date(activityData.end_datetime);
      const eventStart = new Date(selectedEvent.start_date);
      const eventEnd = new Date(selectedEvent.end_date);

      // Validar que las fechas de la actividad estén dentro del rango del evento
      if (activityStart < eventStart) {
        this.dateValidationError = `La fecha de inicio de la actividad no puede ser anterior a la fecha de inicio del evento (${this.formatDateTime(
          eventStart
        )})`;
        return this.dateValidationError;
      }

      if (activityEnd > eventEnd) {
        this.dateValidationError = `La fecha de fin de la actividad no puede ser posterior a la fecha de fin del evento (${this.formatDateTime(
          eventEnd
        )})`;
        return this.dateValidationError;
      }

      // Validar que la fecha de inicio sea anterior a la fecha de fin
      if (activityStart >= activityEnd) {
        this.dateValidationError =
          "La fecha de inicio debe ser anterior a la fecha de fin";
        return this.dateValidationError;
      }

      return null; // Sin errores
    },

    // Delegar formateo de fechas a helpers centralizados cuando estén disponibles
    formatDateTimeForInput(dateTimeString) {
      try {
        const helpers = require("../helpers/dateHelpers");
        return helpers.formatDateTimeForInput(dateTimeString);
      } catch (e) {
        return window.formatDateTimeForInput
          ? window.formatDateTimeForInput(dateTimeString)
          : "";
      }
    },

    formatDate(dateTimeString) {
      try {
        const helpers = require("../helpers/dateHelpers");
        return helpers.formatDate(dateTimeString);
      } catch (e) {
        return window.formatDate
          ? window.formatDate(dateTimeString)
          : "Sin fecha";
      }
    },

    formatDateTime(dateTimeString) {
      try {
        const helpers = require("../helpers/dateHelpers");
        return helpers.formatDateTime(dateTimeString);
      } catch (e) {
        return window.formatDateTime
          ? window.formatDateTime(dateTimeString)
          : "Sin fecha";
      }
    },

    // Consultar actividades relacionadas
    async getRelatedActivities(activityId) {
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const response = await f(`/api/activities/${activityId}/related`);
      if (!response.ok)
        throw new Error("Error al obtener actividades relacionadas");
      const data = await response.json();
      return data.related_activities || [];
    },

    // Enlazar actividad
    async linkActivity(activityId, relatedId) {
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const response = await f(`/api/activities/${activityId}/related`, {
        method: "POST",
        body: JSON.stringify({ related_activity_id: relatedId }),
      });
      if (!response || !response.ok)
        throw new Error("Error al enlazar actividades");
      if (typeof showToast === "function")
        showToast("Actividades enlazadas exitosamente", "success");
    },

    // Desenlazar actividad
    async unlinkActivity(activityId, relatedId) {
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const response = await f(
        `/api/activities/${activityId}/related/${relatedId}`,
        { method: "DELETE" }
      );
      if (!response || !response.ok)
        throw new Error("Error al desenlazar actividades");
      if (typeof showToast === "function")
        showToast("Actividades desenlazadas exitosamente", "success");
    },
    getAvailableActivities() {
      // Usar activityRelations para saber si una actividad está enlazada como A o B
      const linkedIds = new Set();
      this.activityRelations.forEach((act) => {
        if (
          (act.related_activities && act.related_activities.length > 0) ||
          (act.linked_by && act.linked_by.length > 0)
        ) {
          linkedIds.add(act.id);
        }
        if (Array.isArray(act.related_activities)) {
          act.related_activities.forEach((rel) => linkedIds.add(rel.id));
        }
        if (Array.isArray(act.linked_by)) {
          act.linked_by.forEach((rel) => linkedIds.add(rel.id));
        }
      });
      return this.activityRelations.filter(
        (a) =>
          a.event_id === this.currentActivity.event_id && !linkedIds.has(a.id)
      );
    },

    // Cargar relaciones de actividades (A y B)
    async loadActivityRelations() {
      const token = localStorage.getItem("authToken");
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const response = await f("/api/activities/relations");
      if (!response || !response.ok)
        throw new Error("Error al obtener relaciones");
      const data = await response.json();
      this.activityRelations = data.activities || [];
    },
  };
}

// Hacer la función globalmente disponible en navegador
if (typeof window !== "undefined") {
  window.activitiesManager = activitiesManager;
}

// Exportar para Node/Jest (CommonJS)
if (typeof module !== "undefined" && module.exports) {
  module.exports = activitiesManager;
}
