// app/static/js/admin/activity_editor.js
function activityEditorManager() {
  return {
    visible: false,
    loading: false,
    saving: false,
    errorMessage: "",
    editingActivity: false,
    currentActivity: {
      id: null,
      event_id: "",
      department: "",
      name: "",
      description: "",
      start_datetime: "",
      end_datetime: "",
      duration_hours: null,
      activity_type: "",
      location: "",
      modality: "",
      requirements: "",
      knowledge_area: "",
      speakersList: [],
      target_audience_general: false,
      target_audience_careersList: [],
      max_capacity: null,
    },

    init() {
      const listener = async (e) => {
        const detail = e && e.detail ? e.detail : {};
        if (detail.activityId) {
          // Ensure events are loaded so the select can show names
          await this.loadEvents();
          await this.loadActivity(detail.activityId);
          this.visible = true;
        } else if (detail.create) {
          // Load events for the create form too
          await this.loadEvents();
          this.resetCurrent();
          this.editingActivity = false;
          this.visible = true;
        }
      };
      window.addEventListener("open-activity-editor", listener);
      this._openActivityEditorListener = listener;
    },

    async loadActivity(id) {
      this.loading = true;
      this.errorMessage = "";
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(`/api/activities/${id}`);
        if (!response || !response.ok)
          throw new Error(
            `Error al cargar actividad: ${response && response.status}`
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
        this.currentActivity = mapped;
        this.editingActivity = true;
        // if events haven't been loaded yet, load them so the select can resolve names
        if (
          !this.events ||
          !Array.isArray(this.events) ||
          this.events.length === 0
        ) {
          await this.loadEvents();
        }
      } catch (error) {
        console.error("Error loading activity in editor:", error);
        this.errorMessage = error.message || "Error al cargar actividad";
        showToast(this.errorMessage, "error");
      } finally {
        this.loading = false;
      }
    },

    // Cargar eventos para el selector del editor
    async loadEvents() {
      try {
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
        console.error("Error loading events in editor:", error);
        this.events = [];
      }
    },

    resetCurrent() {
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
      this.errorMessage = "";
    },

    async saveActivity() {
      // Client-side guard: require an event association before saving
      if (!this.currentActivity || !this.currentActivity.event_id) {
        this.errorMessage = 'Selecciona un evento antes de guardar la actividad.';
        showToast(this.errorMessage, 'error');
        return;
      }
      this.saving = true;
      this.errorMessage = "";
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const payload = {
          event_id: this.currentActivity.event_id
            ? parseInt(this.currentActivity.event_id)
            : null,
          department: this.currentActivity.department,
          name: this.currentActivity.name,
          description: this.currentActivity.description,
          start_datetime: this.currentActivity.start_datetime,
          end_datetime: this.currentActivity.end_datetime,
          duration_hours:
            this.currentActivity.duration_hours !== null
              ? parseFloat(this.currentActivity.duration_hours)
              : null,
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

        let response;
        if (this.editingActivity && this.currentActivity.id) {
          response = await f(`/api/activities/${this.currentActivity.id}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          });
        } else {
          response = await f(`/api/activities/`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
        }

        if (!response || !response.ok) {
          const err = await (response && response.json
            ? response.json()
            : Promise.resolve({}));
          throw new Error(
            err.message ||
              `Error al guardar actividad: ${response && response.status}`
          );
        }

        const saved = await response.json();
        showToast(
          this.editingActivity ? "Actividad actualizada" : "Actividad creada",
          "success"
        );

        // Notificar a otros managers que refresquen
        window.dispatchEvent(
          new CustomEvent("activity-saved", {
            detail: { id: saved.id || saved.activity?.id },
          })
        );

        // Cerrar editor
        this.visible = false;
        this.resetCurrent();
      } catch (error) {
        console.error("Error saving activity:", error);
        this.errorMessage = error.message || "Error al guardar actividad";
        showToast(this.errorMessage, "error");
      } finally {
        this.saving = false;
      }
    },

    close() {
      this.visible = false;
      this.resetCurrent();
    },
  };
}

// Exponer globalmente
if (typeof window !== "undefined")
  window.activityEditorManager = activityEditorManager;

// Exportar para tests
if (typeof module !== "undefined" && module.exports)
  module.exports = activityEditorManager;
