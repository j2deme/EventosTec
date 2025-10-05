if (j && j.public_token) {
  let url = `/public/registrations/${j.public_token}`;
  if (this.token) {
    url += `?event_token=${encodeURIComponent(this.token)}`;
  }
  window.location.href = url;
} else {
  alert("Respuesta inválida del servidor");
}
if (j && j.public_token) {
  let url = `/public/registrations/${j.public_token}`;
  if (this.token) {
    url += `?event_token=${encodeURIComponent(this.token)}`;
  }
  window.location.href = url;
} else {
  alert("Respuesta inválida del servidor");
}
function eventRegistrationsPublic() {
  return {
    token: null,
    eventId: null,
    q: "",
    activities: [],
    selectedActivity: null,
    showActivityPanel: false,
    activityDeadlineIso: null,
    filters: {
      activity_type: "",
      per_page: 10,
      page: 1,
      department: "",
    },
    pagination: {
      current_page: 1,
      last_page: 1,
      total: 0,
      from: 0,
      to: 0,
      pages: [],
    },
    departments: [],

    init(el) {
      try {
        this.token = el.getAttribute("data-event-token") || "";
        this.eventId = el.getAttribute("data-event-id") || "";
        this.eventName = el.getAttribute("data-event-name") || "";
      } catch (e) {
        // ignore
      }
      this.fetchActivities();
      // Fetch departments for this event to populate the filter
      try {
        if (this.eventId && String(this.eventId).toLowerCase() !== "null") {
          const f =
            typeof window.safeFetch === "function" ? window.safeFetch : fetch;
          f(`/api/events/${encodeURIComponent(this.eventId)}/departments`)
            .then((r) => {
              if (!r.ok) return;
              return r.json();
            })
            .then((j) => {
              if (j && Array.isArray(j.departments))
                this.departments = j.departments;
            })
            .catch(() => {});
        }
      } catch (e) {
        // ignore
      }
    },

    async fetchActivities() {
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;

        const params = new URLSearchParams();
        const page = this.filters.page || 1;
        const per_page = this.filters.per_page || 50;
        params.set("page", page);
        params.set("per_page", per_page);
        if (this.q) params.set("search", this.q);
        if (this.filters.activity_type)
          params.set("activity_type", this.filters.activity_type);
        if (this.filters.department)
          params.set("department", this.filters.department);
        // Request alphabetical order; backend may ignore but we'll sort client-side as fallback
        params.set("sort", "name:asc");

        // Only include event_id if it's a meaningful value (avoid 'null' or empty)
        if (this.eventId && String(this.eventId).toLowerCase() !== "null") {
          params.set("event_id", this.eventId);
        }

        const url = `/api/activities?${params.toString()}`;
        const resp = await f(url);
        if (!resp || !resp.ok) return;
        const data = await resp.json();

        // normalize activities (include current_registrations/current_capacity when provided)
        this.activities = (data.activities || []).map((a) => ({
          id: a.id,
          name: a.name,
          activity_type: a.activity_type || null,
          department: a.department || "",
          start_datetime: a.start_datetime,
          end_datetime: a.end_datetime,
          datesString: a.datesString || null,
          duration_hours: a.duration_hours || null,
          activity_deadline_iso: a.activity_deadline_iso || null,
          // backend may provide either current_registrations or current_capacity
          current_registrations: Number(
            a.current_registrations || a.current_capacity || 0
          ),
        }));

        // Compute date-only display (single day or range without times)
        try {
          this.activities = this.activities.map((act) => {
            try {
              const hasDayjs = typeof dayjs !== "undefined";
              const s = act.start_datetime ? dayjs(act.start_datetime) : null;
              const e = act.end_datetime ? dayjs(act.end_datetime) : null;
              if (hasDayjs && s && s.isValid() && e && e.isValid()) {
                if (s.isSame(e, "day")) {
                  act.dateDisplay = s.format("DD/MM/YY");
                } else {
                  // No mostrar horas, y quitar espacio antes de la abreviatura
                  act.dateDisplay = `${s.format("D")} - ${e.format(
                    "D"
                  )}/${s.format("MMM/YY")}`;
                }
              } else if (act.start_datetime) {
                const sd = new Date(act.start_datetime);
                if (!isNaN(sd)) {
                  const pad = (n) => String(n).padStart(2, "0");
                  const day = (d) => pad(d.getDate());
                  const month = (d) => pad(d.getMonth() + 1);
                  const year2 = (d) => String(d.getFullYear()).slice(-2);
                  act.dateDisplay = `${day(sd)}/${month(sd)}/${year2(sd)}`;
                } else {
                  act.dateDisplay = "Sin fecha";
                }
              } else {
                act.dateDisplay = "Sin fecha";
              }
            } catch (err) {
              act.dateDisplay = act.datesString || "Sin fecha";
            }
            return act;
          });
        } catch (e) {
          // ignore
        }

        // Extract departments list only when there is no eventId (fallback)
        try {
          if (
            !this.eventId ||
            String(this.eventId).toLowerCase() === "" ||
            String(this.eventId).toLowerCase() === "null"
          ) {
            const set = new Set();
            (this.activities || []).forEach((a) => {
              if (a.department) set.add(a.department);
            });
            this.departments = Array.from(set).sort();
          }
        } catch (e) {
          if (!this.departments) this.departments = [];
        }

        // Ensure alphabetical order client-side as fallback
        try {
          this.activities.sort((x, y) =>
            String(x.name || "").localeCompare(String(y.name || ""))
          );
        } catch (e) {
          // ignore
        }

        // pagination (align with admin format)
        const pages = data.pages || 1;
        const current = data.current_page || page;
        const total = data.total || 0;
        this.pagination = {
          current_page: current,
          last_page: pages,
          total: total,
          from: (current - 1) * per_page + 1,
          to: Math.min(current * per_page, total),
          pages: Array.from({ length: pages }, (_, i) => i + 1),
        };
      } catch (e) {
        console.error("fetchActivities", e);
      }
    },

    openActivity(a) {
      this.selectedActivity = a;
      this.showActivityPanel = true;
    },

    closeActivityPanel() {
      this.selectedActivity = null;
      this.showActivityPanel = false;
    },

    async openRegistrationsForSelected() {
      if (!this.selectedActivity) return;
      // Request a public activity token from server, then redirect without exposing activity id
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const eventRef = this.token || this.eventId;
        if (!eventRef) {
          console.error(
            "Missing event token/id for generating public activity token"
          );
          alert("No se pudo generar el link público: token de evento ausente");
          return;
        }
        const resp = await f(
          `/api/public/event/${encodeURIComponent(eventRef)}/activity-token`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ activity_id: this.selectedActivity.id }),
          }
        );
        if (!resp) {
          alert("Error de red al generar el link");
          return;
        }
        if (!resp.ok) {
          const j = await resp.json().catch(() => ({}));
          console.error("server error", j);
          alert(j.message || "Error generando link público");
          return;
        }
        const j = await resp.json();
        if (j && j.public_token) {
          window.location.href = `/public/registrations/${j.public_token}`;
        } else {
          alert("Respuesta inválida del servidor");
        }
      } catch (e) {
        console.error("openRegistrationsForSelected", e);
      }
    },

    async openRegistrationsForActivity(a) {
      if (!a) return;
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const eventRef = this.token || this.eventId;
        if (!eventRef) {
          console.error(
            "Missing event token/id for generating public activity token"
          );
          alert("No se pudo generar el link público: token de evento ausente");
          return;
        }
        const resp = await f(
          `/api/public/event/${encodeURIComponent(eventRef)}/activity-token`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ activity_id: a.id }),
          }
        );
        if (!resp) {
          alert("Error de red al generar el link");
          return;
        }
        if (!resp.ok) {
          const j = await resp.json().catch(() => ({}));
          console.error("server error", j);
          alert(j.message || "Error generando link público");
          return;
        }
        const j = await resp.json();
        if (j && j.public_token) {
          window.location.href = `/public/registrations/${j.public_token}`;
        } else {
          alert("Respuesta inválida del servidor");
        }
      } catch (e) {
        console.error("openRegistrationsForActivity", e);
      }
    },

    async downloadRegistrationsForActivity(a) {
      if (!a) return;
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        // Use the event-level token if provided by the surrounding page (this.token)
        // If this.token is an event token (pe:...), server expects activity id in body.
        const payload = { token: this.token || this.eventId };
        // If token looks like an event-level token (starts with 'pe:'), include activity id
        const t = payload.token || "";
        if (String(t).startsWith("pe:")) {
          payload.activity = a.id;
        }

        const resp = await f("/api/public/registrations/export", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!resp) {
          alert("Error de red al solicitar el archivo");
          return;
        }

        if (!resp.ok) {
          const j = await resp.json().catch(() => ({}));
          alert(j.message || "Error generando el archivo");
          return;
        }

        const blob = await resp.blob();
        // Try to obtain filename from Content-Disposition header
        const cd = resp.headers.get("Content-Disposition") || "";
        let filename = `${(a.name || "actividad").replace(
          /[^a-z0-9A-Z-_\.]/g,
          "_"
        )}.xlsx`;
        const m = /filename\*=UTF-8''([^;]+)/i.exec(cd);
        if (m && m[1]) {
          try {
            filename = decodeURIComponent(m[1]);
          } catch (e) {}
        } else {
          const m2 = /filename="?([^\"]+)"?/i.exec(cd);
          if (m2 && m2[1]) filename = m2[1];
        }

        const url = window.URL.createObjectURL(blob);
        const ael = document.createElement("a");
        ael.href = url;
        ael.download = filename;
        document.body.appendChild(ael);
        ael.click();
        ael.remove();
        window.URL.revokeObjectURL(url);
      } catch (e) {
        console.error("downloadRegistrationsForActivity", e);
        alert("Error al descargar el archivo");
      }
    },

    changePage(page) {
      if (!page || page < 1) return;
      this.filters.page = page;
      this.fetchActivities();
    },

    formatDeadline(iso) {
      try {
        if (window.dayjs) return window.dayjs(iso).format("YYYY-MM-DD HH:mm");
        return new Date(iso).toLocaleString();
      } catch (e) {
        return iso;
      }
    },
  };
}

window.eventRegistrationsPublic = eventRegistrationsPublic;
