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
      per_page: 20,
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
    // track whether we've already fetched the full departments list for the current event
    _departmentsLoadedForEvent: null,
    // show loading overlay while activities are being fetched
    loadingActivities: false,

    init(el) {
      try {
        this.token = "";
        // normalize eventId: accept only integer-like values, else null
        const rawEventId = el.getAttribute("data-event-id") || "";
        this.eventId = /^\d+$/.test(String(rawEventId || "").trim())
          ? Number(String(rawEventId).trim())
          : null;
        // read eventSlug (if provided) as fallback
        this.eventSlug = el.getAttribute("data-event-slug") || null;
        this.eventName = el.getAttribute("data-event-name") || "";
        const initialActivityId =
          el.getAttribute("data-initial-activity-id") || "";
        // If the server injected an initial activity id/slug, immediately open it
        if (initialActivityId) {
          window.location.href = `/public/registrations/${encodeURIComponent(
            initialActivityId,
          )}`;
          return;
        }
      } catch (e) {
        // ignore
      }
      // Only fetch activities if we have a meaningful eventId. Avoid
      // performing an unfiltered request that returns activities from other
      // events (this caused the duplicated-list confusion).
      if (this.eventId && String(this.eventId).toLowerCase() !== "null") {
        this.fetchActivities();
      }
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
              // remember we loaded departments for this event so we don't refetch unnecessarily
              this._departmentsLoadedForEvent = this.eventId;
            })
            .catch(() => {});
        }
      } catch (e) {
        // ignore
      }
    },

    async fetchActivities() {
      try {
        // mark loading state so template can show spinner overlay
        this.loadingActivities = true;
        // Defensive: do not perform an unfiltered activities request from the
        // public event page. If the caller invoked this without an eventId we
        // must avoid returning unrelated activities. The component expects an
        // eventId to be provided by the server-rendered template.
        if (!this.eventId || String(this.eventId).toLowerCase() === "null") {
          this.loadingActivities = false;
          return;
        }
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
        if (!resp || !resp.ok) {
          this.loadingActivities = false;
          return;
        }
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
            a.current_registrations || a.current_capacity || 0,
          ),
          // UI flags
          _loading_copy: false,
          _loading_manage: false,
          _loading_download: false,
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
                    "D",
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

        // If we have an eventId, ensure we fetch the full departments list at least once
        // (the paginated activities response may only include a subset of departments).
        try {
          if (
            this.eventId &&
            String(this.eventId).toLowerCase() !== "null" &&
            this._departmentsLoadedForEvent !== this.eventId
          ) {
            const f =
              typeof window.safeFetch === "function" ? window.safeFetch : fetch;
            f(`/api/events/${encodeURIComponent(this.eventId)}/departments`)
              .then((r) => {
                if (!r.ok) return;
                return r.json();
              })
              .then((j) => {
                if (j && Array.isArray(j.departments) && j.departments.length) {
                  this.departments = j.departments;
                  this._departmentsLoadedForEvent = this.eventId;
                }
              })
              .catch(() => {});
          }
        } catch (e) {
          // ignore
        }

        // Ensure alphabetical order client-side as fallback
        try {
          this.activities.sort((x, y) =>
            String(x.name || "").localeCompare(String(y.name || "")),
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
        // finished loading
        this.loadingActivities = false;
      } catch (e) {
        console.error("fetchActivities", e);
        this.loadingActivities = false;
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
        // Prefer server-provided event slug first, then event token, then numeric eventId
        let eventRef =
          this.eventSlug ||
          this.token ||
          (Number.isInteger(this.eventId) ? String(this.eventId) : null);
        if (!eventRef) {
          // Without an eventRef (token/id/slug) we must not generate slugs client-side.
          // The server is authoritative for slugs; instruct the user/admin to use the server-provided event link.
          console.error(
            "Missing event token/id for generating public activity token",
          );
          alert(
            "No se pudo generar el link público: token de evento ausente. Use el enlace proporcionado por el servidor para este evento.",
          );
          return;
        }
        const resp = await f(
          `/api/public/event/${encodeURIComponent(eventRef)}/activity-slug`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ activity_id: this.selectedActivity.id }),
          },
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
        if (j && j.activity_slug) {
          // Redirect using activity slug only (no query params)
          window.location.href = `/public/registrations/${encodeURIComponent(
            j.activity_slug,
          )}`;
        } else {
          alert("Respuesta inválida del servidor");
        }
      } catch (e) {
        console.error("openRegistrationsForSelected", e);
      }
    },

    async openRegistrationsForActivity(a) {
      if (!a) return;
      // mark loading state for this activity to provide UI feedback
      a._loading_manage = true;
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        // Prefer server-provided event slug first, then event token, then numeric eventId
        let eventRef =
          this.eventSlug ||
          this.token ||
          (Number.isInteger(this.eventId) ? String(this.eventId) : null);
        if (!eventRef) {
          // Do not construct slugs in the client. Server must provide event slug or token.
          console.error(
            "Missing event token/id for generating public activity token",
          );
          alert(
            "No se pudo generar el link público: token de evento ausente. Use el enlace proporcionado por el servidor para este evento.",
          );
          a._loading_manage = false;
          return;
        }
        const resp = await f(
          `/api/public/event/${encodeURIComponent(eventRef)}/activity-slug`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ activity_id: a.id }),
          },
        );
        if (!resp) {
          alert("Error de red al generar el link");
          a._loading_manage = false;
          return;
        }
        if (!resp.ok) {
          const j = await resp.json().catch(() => ({}));
          console.error("server error", j);
          alert(j.message || "Error generando link público");
          a._loading_manage = false;
          return;
        }
        const j = await resp.json();
        if (j && j.activity_slug) {
          // telemetry: log which activity requested a slug
          try {
            console.debug("activity-slug-generated", { activity: a.id });
          } catch (e) {}
          // Redirect using activity slug only (no query params)
          window.location.href = `/public/registrations/${encodeURIComponent(
            j.activity_slug,
          )}`;
        } else {
          alert("Respuesta inválida del servidor");
          a._loading_manage = false;
        }
      } catch (e) {
        console.error("openRegistrationsForActivity", e);
        a._loading_manage = false;
      }
    },

    async copyLinkForActivity(a, ev) {
      if (!a) return;
      // set loading flag to update button state
      a._loading_copy = true;
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        // Prefer server-provided event slug first, then event token, then numeric eventId
        let eventRef =
          this.eventSlug ||
          this.token ||
          (Number.isInteger(this.eventId) ? String(this.eventId) : null);
        if (!eventRef) {
          // Do not generate slugs client-side. Inform user to use server-provided link.
          console.error(
            "Missing event token/id for generating public activity token",
          );
          if (typeof showToast === "function")
            showToast(
              "No se pudo generar el link público: token de evento ausente. Use el enlace proporcionado por el servidor.",
              "error",
            );
          else
            alert(
              "No se pudo generar el link público: token de evento ausente. Use el enlace proporcionado por el servidor.",
            );
          a._loading_copy = false;
          return;
        }
        // Request activity slug from server and build public registrations URL
        const resp = await f(
          `/api/public/event/${encodeURIComponent(eventRef)}/activity-slug`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ activity_id: a.id }),
          },
        );
        if (!resp) {
          if (typeof showToast === "function")
            showToast("Error de red al generar el link", "error");
          else alert("Error de red al generar el link");
          a._loading_copy = false;
          return;
        }
        if (!resp.ok) {
          const j = await resp.json().catch(() => ({}));
          console.error("server error", j);
          if (typeof showToast === "function")
            showToast(j.message || "Error generando link público", "error");
          else alert(j.message || "Error generando link público");
          a._loading_copy = false;
          return;
        }
        const j = await resp.json();
        if (j && j.activity_slug) {
          const url = `${
            location.origin
          }/public/registrations/${encodeURIComponent(j.activity_slug)}`;
          // telemetry / debug
          try {
            console.debug("copy-link", { activity: a.id });
          } catch (e) {}
          // copy to clipboard
          try {
            await navigator.clipboard.writeText(url);
            if (typeof showToast === "function") {
              showToast("Enlace copiado al portapapeles");
            } else {
              // tooltip fallback near the clicked element
              try {
                const btn =
                  ev && ev.currentTarget
                    ? ev.currentTarget
                    : document.activeElement;
                const tip = document.createElement("div");
                tip.textContent = "Enlace copiado";
                tip.style.position = "absolute";
                tip.style.background = "#111827";
                tip.style.color = "white";
                tip.style.padding = "6px 8px";
                tip.style.borderRadius = "6px";
                tip.style.zIndex = 10000;
                document.body.appendChild(tip);
                const rect = btn.getBoundingClientRect();
                tip.style.left = rect.left + window.scrollX + "px";
                tip.style.top = rect.top + window.scrollY - 36 + "px";
                setTimeout(() => tip.remove(), 2000);
              } catch (e) {
                // final fallback: alert
                alert("Enlace copiado al portapapeles: " + url);
              }
            }
            a._loading_copy = false;
          } catch (e) {
            // Fallback: create a temporary element
            const ta = document.createElement("textarea");
            ta.value = url;
            document.body.appendChild(ta);
            ta.select();
            try {
              document.execCommand("copy");
              if (typeof showToast === "function")
                showToast("Enlace copiado al portapapeles");
              else alert("Enlace copiado al portapapeles: " + url);
            } catch (err) {
              alert("No se pudo copiar el enlace. Aquí está: " + url);
            }
            ta.remove();
            a._loading_copy = false;
          }
        } else {
          if (typeof showToast === "function")
            showToast("Respuesta inválida del servidor", "error");
          else alert("Respuesta inválida del servidor");
          a._loading_copy = false;
        }
      } catch (e) {
        console.error("copyLinkForActivity", e);
        a._loading_copy = false;
      }
    },

    async downloadRegistrationsForActivity(a) {
      if (!a) return;
      a._loading_download = true;
      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        // Prefer server-provided event slug first, then event token, then numeric eventId
        let eventRef =
          this.eventSlug ||
          this.token ||
          (Number.isInteger(this.eventId) ? String(this.eventId) : null);
        const payload = {};
        if (eventRef) {
          payload.token = eventRef;
          // If token looks like an event-level token (starts with 'pe:'), include activity id
          if (String(eventRef).startsWith("pe:")) payload.activity = a.id;
        } else {
          // If no eventRef, we must not fabricate slugs client-side. Abort and require server-provided event reference.
          if (typeof showToast === "function")
            showToast(
              "No se pudo generar el archivo: token de evento ausente. Use el enlace proporcionado por el servidor.",
              "error",
            );
          else
            alert(
              "No se pudo generar el archivo: token de evento ausente. Use el enlace proporcionado por el servidor.",
            );
          a._loading_download = false;
          return;
        }
        // If token looks like an event-level token (starts with 'pe:'), include activity id
        const t = payload.token || "";
        if (String(t).startsWith("pe:")) {
          payload.activity = a.id;
        }

        // call export endpoint passing activity_id directly
        const resp = await f("/api/public/registrations/export", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ activity_id: a.id }),
        });

        if (!resp) {
          if (typeof showToast === "function")
            showToast("Error de red al solicitar el archivo", "error");
          else alert("Error de red al solicitar el archivo");
          a._loading_download = false;
          return;
        }

        if (!resp.ok) {
          const j = await resp.json().catch(() => ({}));
          if (typeof showToast === "function")
            showToast(j.message || "Error generando el archivo", "error");
          else alert(j.message || "Error generando el archivo");
          a._loading_download = false;
          return;
        }

        const blob = await resp.blob();
        // Try to obtain filename from Content-Disposition header
        const cd = resp.headers.get("Content-Disposition") || "";
        let filename = `${(a.name || "actividad").replace(
          /[^a-z0-9A-Z-_\.]/g,
          "_",
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
        a._loading_download = false;
      } catch (e) {
        console.error("downloadRegistrationsForActivity", e);
        if (typeof showToast === "function")
          showToast("Error al descargar el archivo", "error");
        else alert("Error al descargar el archivo");
        a._loading_download = false;
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
