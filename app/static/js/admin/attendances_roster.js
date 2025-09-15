// app/static/js/admin/attendances_roster.js
function attendancesRoster() {
  return {
    events: [],
    activities: [],
    registrations: [],
    selectedEvent: "",
    selectedActivity: "",
    selectedIds: new Set(),
    loading: false,

    init() {
      this.loadEvents();
    },

    async loadEvents() {
      try {
        const res = await fetch("/api/events?status=active&per_page=1000");
        if (!res.ok) throw new Error("No se pudieron cargar eventos");
        const data = await res.json();
        this.events = data.events || [];
      } catch (err) {
        console.error(err);
        showToast("Error al cargar eventos", "error");
      }
    },

    async loadActivities() {
      if (!this.selectedEvent) {
        this.activities = [];
        return;
      }
      try {
        const res = await fetch(
          `/api/activities?event_id=${this.selectedEvent}&per_page=1000`
        );
        if (!res.ok) throw new Error("No se pudieron cargar actividades");
        const data = await res.json();
        this.activities = data.activities || [];
      } catch (err) {
        console.error(err);
        showToast("Error al cargar actividades", "error");
      }
    },

    async loadRegistrations() {
      if (!this.selectedActivity) {
        this.registrations = [];
        return;
      }
      this.loading = true;
      try {
        const res = await fetch(
          `/api/registrations?activity_id=${this.selectedActivity}&per_page=1000`
        );
        if (!res.ok) throw new Error("Error al cargar preregistros");
        const data = await res.json();
        this.registrations = data.registrations || [];
        // Limpiar selección
        this.selectedIds = new Set();
      } catch (err) {
        console.error(err);
        showToast("Error al cargar preregistros", "error");
      } finally {
        this.loading = false;
      }
    },

    toggleSelection(reg) {
      if (this.selectedIds.has(reg.id)) {
        this.selectedIds.delete(reg.id);
      } else {
        this.selectedIds.add(reg.id);
      }
    },

    isSelected(reg) {
      return this.selectedIds.has(reg.id);
    },

    toggleSelectAll(e) {
      if (e.target.checked) {
        this.registrations.forEach((r) => this.selectedIds.add(r.id));
      } else {
        this.selectedIds = new Set();
      }
    },

    async markSelected() {
      if (!this.selectedActivity) {
        showToast("Selecciona una actividad primero", "warning");
        return;
      }
      if (this.selectedIds.size === 0) {
        showToast("Selecciona al menos un preregistro", "warning");
        return;
      }

      const studentIds = [];
      // Convert registration ids to student ids by lookup
      this.registrations.forEach((r) => {
        if (this.selectedIds.has(r.id)) {
          if (r.student && r.student.id) studentIds.push(r.student.id);
        }
      });

      if (studentIds.length === 0) {
        showToast(
          "No se encontró estudiante para los preregistros seleccionados",
          "error"
        );
        return;
      }

      try {
        const res = await fetch("/api/attendances/bulk-create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            activity_id: Number(this.selectedActivity),
            student_ids: studentIds,
          }),
        });
        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          showToast(body.message || "Asistencias creadas", "success");
          // recargar lista
          await this.loadRegistrations();
        } else {
          showToast(body.message || "Error al marcar asistentes", "error");
        }
      } catch (err) {
        console.error(err);
        showToast("Error al marcar asistentes", "error");
      }
    },

    printRoster() {
      // Generar una ventana con la tabla minimal para imprimir
      const rows = this.registrations
        .map((r) => {
          const name =
            (r.student && (r.student.full_name || r.student.name)) ||
            "Desconocido";
          const control = (r.student && r.student.control_number) || "";
          const activity = (r.activity && r.activity.name) || "";
          return `<tr><td style="padding:4px;border:1px solid #ddd">${name}</td><td style="padding:4px;border:1px solid #ddd">${control}</td><td style="padding:4px;border:1px solid #ddd">${activity}</td><td style="padding:4px;border:1px solid #ddd">_____</td></tr>`;
        })
        .join("");

      const html = `<!doctype html><html><head><meta charset="utf-8"><title>Roster</title><style>table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:8px}</style></head><body><h3>Roster - ${
        this.activities.find((a) => a.id == this.selectedActivity)?.name || ""
      }</h3><table><thead><tr><th>Estudiante</th><th>Control</th><th>Actividad</th><th>Firma</th></tr></thead><tbody>${rows}</tbody></table></body></html>`;
      const w = window.open("", "_blank");
      w.document.write(html);
      w.document.close();
      w.print();
    },
  };
}

// Export factory for Alpine
window.attendancesRoster = attendancesRoster;
