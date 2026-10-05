// static/js/admin/calendar.js
// Vista calendario: distribución de actividades por día y horario de un evento.
function calendarAdmin() {
  // Caché NO reactiva del cronograma de un día: daySchedule() se lee varias
  // veces durante el mismo render de la plantilla y recalcularlo en cada
  // acceso dispararía otro render. Se invalida sola porque guarda la
  // referencia del objeto `calendar` que la produjo (cada recarga crea uno
  // nuevo).
  const schedCache = { src: undefined, day: null, value: null };

  // Desde cuántos carriles paralelos la tarjeta queda demasiado angosta para
  // leer el título en horizontal (a 6 carriles el ancho efectivo ronda los
  // 100 px en escritorio y 60 px en móvil): a partir de ahí el bloque de
  // texto se gira para leerse de abajo hacia arriba.
  const ROTATE_LANES = 6;

  // Ancho mínimo de un carril. El lienzo mide `CANAL_HORAS (56) + carriles
  // * LANE_MIN_PX`; con un min-w fijo de 680 px, 19 carriles daban 33 px en
  // móvil = UNA sola columna de texto (6 caracteres). Con 56 px siempre hay
  // 3 columnas (44 px de texto / 14 px de interlínea), en cualquier
  // dispositivo.
  const LANE_MIN_PX = 56;
  const CANAL_HORAS = 56; // w-14 del canal de horas
  const CAL_MIN_PX = 680; // suelo para días con pocos carriles

  // Ancho de la tarjeta al pasar el cursor (estilo Google Calendar): se
  // ensancha por encima de los vecinos y muestra el nombre completo en
  // horizontal. Sin transición en `width` para no crear estados intermedios
  // en los que el puntero quede fuera y se dispare un bucle de hover.
  const HOVER_W = 240;

  // A partir de qué duración la tira girada añade ubicación, cupo y sesión.
  // Por debajo solo caben el nombre y el horario: la hora ya la dice la
  // posición en el eje, y el resto (incluida `Sesión n/m`) aparece entero al
  // pasar el cursor, con la tarjeta expandida.
  const TIER_FULL_HOURS = 4;

  // --- Ficha horizontal (tarjeta ancha o expandida al pasar el cursor) ------
  //
  // El ALTO de la tarjeta lo fija el eje de horas, no el contenido, así que
  // si se meten más filas de las que caben la última queda cortada por la
  // mitad en el borde inferior. Por eso los bloques extra se habilitan por
  // ALTURA y no por ancho: 2 h (176 px), 3 h (264 px) y 4 h (352 px). Con los
  // datos reales del 46 aniversario eso abre la fila de ubicación en 54 de
  // 59 sesiones, el bloque profundo en 39 y los requisitos en 33; las 5
  // sesiones de 1 h se quedan con cabecera + título, que ya caben enteros.
  const FULL_LOC_H = 176; // 2 h: duración · ubicación · modalidad
  const FULL_DEEP_H = 264; // 3 h: departamento · ponentes · descripción
  const FULL_REQ_H = 352; // 4 h: requisitos

  return {
    // Estado
    loading: false,
    errorMessage: "",
    events: [],
    selectedEventId: null,
    calendar: null, // {event, days, activities, total_activities}
    showDetail: false,
    selectedActivity: null,

    // Vista activa: "range" (una columna por día, por defecto) o "day"
    // (horario de UN día, con carriles para lo simultáneo)
    viewMode: "range",
    selectedDay: null,

    // Tarjeta del timeline que está bajo el cursor (ver cardStyle/isHovered)
    hoveredId: null,

    // Día resaltado en el índice sticky (ver updateActiveDay)
    activeDay: null,
    _spyHandler: null,
    _spyRaf: null,
    _spyUnload: null,
    _spyScroller: null,

    // Inicialización
    async init() {
      this.showDetail = false;
      this.selectedActivity = null;
      this.initDaySpy();

      // Lazy-init (Fase D): diferir la carga hasta la pestaña "calendar"
      await window.tabLazyBoot("calendar", () => this.loadEvents());
    },

    // Cargar lista de eventos (selector) y auto-seleccionar el primero
    async loadEvents() {
      this.loading = true;
      this.errorMessage = "";

      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(
          "/api/events/?page=1&per_page=100&sort=start_date:desc",
        );
        if (!response.ok) {
          throw new Error("Error al cargar los eventos");
        }
        const data = await response.json();
        this.events = (data && data.events) || [];

        if (this.events.length > 0) {
          this.selectedEventId = String(this.events[0].id);
          await this.loadCalendar(this.selectedEventId);
        }
      } catch (e) {
        this.errorMessage = (e && e.message) || "Error al cargar los eventos";
      } finally {
        this.loading = false;
      }
    },

    // Cambio de evento en el selector
    async onEventChange() {
      if (this.selectedEventId) {
        await this.loadCalendar(this.selectedEventId);
      }
    },

    // Cargar calendario del evento seleccionado
    async loadCalendar(eventId) {
      if (!eventId) return;
      this.loading = true;
      this.errorMessage = "";
      this.calendar = null;

      try {
        const f =
          typeof window.safeFetch === "function" ? window.safeFetch : fetch;
        const response = await f(`/api/events/${eventId}/calendar`);
        if (!response.ok) {
          throw new Error("Error al cargar el calendario");
        }
        this.calendar = await response.json();
        // El día seleccionado en la vista "horario" debe seguir existiendo
        const days = (this.calendar && this.calendar.days) || [];
        if (days.indexOf(this.selectedDay) === -1) {
          this.selectedDay = days[0] || null;
        }
      } catch (e) {
        this.errorMessage = (e && e.message) || "Error al cargar el calendario";
      } finally {
        this.loading = false;
        // El resaltado depende de las cajas ya renderizadas (x-show): esperar
        // al siguiente tick de Alpine. Sin $nextTick (tests) se calcula ya.
        if (typeof this.$nextTick === "function") {
          this.$nextTick(() => this.updateActiveDay());
        } else {
          this.updateActiveDay();
        }
      }
    },

    // --- Helpers de vista ---

    // Actividades de un día, ordenadas por hora de inicio
    dayActivities(dayIso) {
      if (!this.calendar) return [];
      return (this.calendar.activities || [])
        .filter((a) => a.day === dayIso)
        .sort((a, b) => (a.starts_at || "").localeCompare(b.starts_at || ""));
    },

    // Actividades fuera de la ventana del evento (o sin fecha)
    outsideActivities() {
      if (!this.calendar) return [];
      const days = this.calendar.days || [];
      return (this.calendar.activities || []).filter(
        (a) => !a.day || days.indexOf(a.day) === -1,
      );
    },

    // Contador de actividades de un día (para el encabezado de la columna)
    dayCount(dayIso) {
      return this.dayActivities(dayIso).length;
    },

    // Etiqueta de día legible. Parseo manual de "YYYY-MM-DD" para evitar el
    // corrimiento de zona que produce new Date("YYYY-MM-DD") (UTC midnight).
    dayLabel(dayIso) {
      const parts = String(dayIso)
        .split("-")
        .map((n) => parseInt(n, 10));
      if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) {
        return String(dayIso);
      }
      const d = new Date(parts[0], parts[1] - 1, parts[2]);
      return d.toLocaleDateString("es-MX", {
        weekday: "short",
        day: "numeric",
        month: "short",
      });
    },

    // --- Presentación por tipo (delegado al helper compartido con la vista
    //     del estudiante: window.activityTypeHelpers) ---

    typeHelpers() {
      return (
        (typeof window !== "undefined" && window.activityTypeHelpers) || null
      );
    },

    // Superficie del chip: borde fuerte + fondo suave + texto por tipo
    typeColor(type) {
      const h = this.typeHelpers();
      if (h && typeof h.color === "function") return h.color(type);
      // Fallback si el helper no cargó: neutro, nunca rompe el layout
      return "border-gray-400 bg-gray-50 text-gray-800";
    },

    // Círculo con el icono del tipo
    typeSoft(type) {
      const h = this.typeHelpers();
      if (h && typeof h.soft === "function") return h.soft(type);
      return "bg-gray-100 text-gray-600";
    },

    // Icono semántico del tipo (ti-school, ti-presentation, …)
    typeIcon(type) {
      const h = this.typeHelpers();
      if (h && typeof h.icon === "function") return h.icon(type);
      return "ti-tag";
    },

    // "registrados/cupo" — solo si hay cupo definido
    cupoLabel(activity) {
      if (!activity || activity.max_capacity == null) return "";
      return `${activity.registered_count || 0}/${activity.max_capacity}`;
    },

    // Estado del cupo para colorear el chip: "full" | "high" | "ok" | "none".
    // El mapa a clases Tailwind vive en la plantilla (literales, para que
    // Tailwind CDN las genere).
    cupoLevel(activity) {
      if (!activity || activity.max_capacity == null) return "none";
      const registered = activity.registered_count || 0;
      const max = activity.max_capacity;
      if (max <= 0) return "none";
      if (registered >= max) return "full";
      if (registered / max >= 0.9) return "high";
      return "ok";
    },

    // Duración POR SESIÓN (inicio–fin de ESTE día, no duration_hours total).
    sessionDuration(activity) {
      if (!activity) return "";
      const h = this.typeHelpers();
      if (h && typeof h.durationBetween === "function") {
        const d = h.durationBetween(activity.starts_at, activity.ends_at);
        if (d) return d;
      }
      // Sin horario de sesión: se cae al total del activity (mejor que nada)
      return activity.duration_hours != null
        ? `${activity.duration_hours} h`
        : "";
    },

    // Scroll suave a la columna de un día desde el índice sticky
    scrollToDay(dayIso) {
      const el = document.getElementById(`cal-day-${dayIso}`);
      if (!el) return;
      if (typeof el.scrollIntoView === "function") {
        el.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
          inline: "center",
        });
      }
    },

    // Columnas del grid: una por día del evento (el ancho depende del evento,
    // por eso style inline en lugar de clases dinámicas)
    gridStyle() {
      const n =
        (this.calendar && this.calendar.days && this.calendar.days.length) || 1;
      return `grid-template-columns: repeat(${Math.max(n, 1)}, minmax(200px, 1fr));`;
    },

    // --- Selector de vista --------------------------------------------------

    // Cambia entre la vista por defecto (rango de días) y la vista de
    // horario de un solo día. Al entrar en "day" se fija el día a mostrar:
    // el que se le pasó, o el que ya estaba, o el que se veía en rango.
    setView(mode, dayIso) {
      const days = (this.calendar && this.calendar.days) || [];
      this.hoveredId = null;
      this.viewMode = mode === "day" ? "day" : "range";
      if (this.viewMode !== "day") return;
      let pick = null;
      for (const cand of [dayIso, this.selectedDay, this.activeDay]) {
        if (cand && days.indexOf(cand) !== -1) {
          pick = cand;
          break;
        }
      }
      this.selectedDay = pick || days[0] || null;
    },

    // Clic en una píldora del índice sticky: en modo rango hace scroll a la
    // columna; en modo horario cambia el día mostrado.
    onDayPillClick(dayIso) {
      if (this.viewMode === "day") {
        this.hoveredId = null;
        this.selectedDay = dayIso;
        return;
      }
      this.scrollToDay(dayIso);
    },

    // ¿Esta píldora se pinta de indigo? En modo horario marca el día
    // seleccionado; en modo rango, la columna visible (solo en móvil).
    isDayActive(dayIso) {
      if (this.viewMode === "day") return this.selectedDay === dayIso;
      return this.activeDay === dayIso;
    },

    // --- Vista "horario" de un día (tipo Google Calendar) -------------------
    //
    // Devuelve {hourFrom, hourTo, hours, hourPx, height, maxLanes, items,
    // unscheduled}. Cada item lleva {activity, start, end, lane, lanes,
    // style}: las actividades que se solapan se reparten en carriles
    // paralelos, que es lo que hace visible lo que ocurre a la misma hora.
    //
    // Con muchas simultáneas cada carril queda muy angosto (el 08/09 oct del
    // 46 aniversario llega a 19) y el título no cabe en horizontal. Ahí
    // isNarrow() manda a girar el bloque de texto: se lee de abajo hacia
    // arriba y aprovecha el ALTO de la tarjeta en lugar del ancho, sin
    // perder el eje de horas. El nivel de detalle de esa tira lo decide
    // schedTier() y el ancho mínimo de los carriles, schedMinWidth().

    // "HH:MM" -> minutos desde medianoche (null si no parsea)
    _toMin(hhmm) {
      const m = /^(\d{1,2}):(\d{2})/.exec(
        String(hhmm == null ? "" : hhmm).trim(),
      );
      if (!m) return null;
      const h = parseInt(m[1], 10);
      const mi = parseInt(m[2], 10);
      if (h > 24 || mi > 59) return null;
      return h * 60 + mi;
    },

    hourLabel(h) {
      return `${String(h).padStart(2, "0")}:00`;
    },

    daySchedule(dayIso) {
      if (
        schedCache.src === this.calendar &&
        schedCache.day === dayIso &&
        schedCache.value
      ) {
        return schedCache.value;
      }

      // Zoom del eje de horas. Con 64 px una tarjeta de 1 h solo tenía 36 px
      // para el texto (6 caracteres/columna); con 88 px hay 80 → 13, que con
      // 3 columnas dan 39 caracteres de nombre. Es un zoom puro: no miente
      // sobre la duración, solo escala el eje.
      const HOUR_PX = 88;
      const DAY_END = 24 * 60;
      const items = [];
      const unscheduled = [];

      for (const a of this.dayActivities(dayIso)) {
        const s = this._toMin(a.starts_at);
        if (s == null || s >= DAY_END) {
          unscheduled.push(a);
          continue;
        }
        let e = this._toMin(a.ends_at);
        if (e == null || e <= s) e = s + 60; // sin fin o fin ya pasado: 1 h
        if (e > DAY_END) e = DAY_END; // sesión que cruza la medianoche
        items.push({
          activity: a,
          id: a.id,
          start: s,
          end: e,
          lane: 0,
          lanes: 1,
        });
      }
      items.sort(
        (x, y) =>
          x.start - y.start ||
          x.end - y.end ||
          Number(x.id) - Number(y.id) ||
          0,
      );

      // 1) Clusters: grupos de actividades que se tocan entre sí. El primer
      //    item que arranca cuando ya terminaron todos abre un grupo nuevo.
      const clusters = [];
      let cur = null;
      for (const it of items) {
        if (!cur || it.start >= cur.end) {
          cur = { end: it.end, items: [] };
          clusters.push(cur);
        }
        cur.items.push(it);
        if (it.end > cur.end) cur.end = it.end;
      }

      // 2) Dentro de cada cluster, carril greedy: el primero que ya quedó
      //    libre. Como los items entran ordenados por hora, esto reparte lo
      //    simultáneo en columnas paralelas con el mínimo de carriles.
      for (const cl of clusters) {
        const laneEnd = [];
        for (const it of cl.items) {
          let lane = -1;
          for (let k = 0; k < laneEnd.length; k++) {
            if (laneEnd[k] <= it.start) {
              lane = k;
              break;
            }
          }
          if (lane === -1) {
            lane = laneEnd.length;
            laneEnd.push(0);
          }
          laneEnd[lane] = it.end;
          it.lane = lane;
        }
        const lanes = Math.max(laneEnd.length, 1);
        for (const it of cl.items) it.lanes = lanes;
      }

      // 3) Ventana horaria: de la primera hora de inicio a la última de fin
      let hourFrom = 8;
      let hourTo = 18;
      if (items.length) {
        let maxEnd = 0;
        for (const it of items) if (it.end > maxEnd) maxEnd = it.end;
        hourFrom = Math.max(0, Math.min(Math.floor(items[0].start / 60), 23));
        hourTo = Math.min(24, Math.max(Math.ceil(maxEnd / 60), hourFrom + 1));
      }
      const hours = [];
      for (let h = hourFrom; h < hourTo; h++) hours.push(h);

      // 4) Posición en píxeles (top/height) y en % (lane/lanes)
      for (const it of items) {
        const top = ((it.start - hourFrom * 60) / 60) * HOUR_PX;
        const h = Math.max(((it.end - it.start) / 60) * HOUR_PX, 26);
        const leftPct = ((it.lane * 100) / it.lanes).toFixed(4);
        const widthPct = (100 / it.lanes).toFixed(4);
        // `geom` es la fuente para cardStyle(), que puede sobrescribir el
        // ancho cuando la tarjeta está bajo el cursor. `style` se mantiene
        // como la cadena ya resuelta (lo que usa el DOM y los tests).
        it.geom = {
          top: Math.round(top),
          height: Math.round(h),
          leftPct,
          widthPct,
        };
        it.style =
          `top:${Math.round(top)}px;height:${Math.round(h)}px;` +
          `left:calc(${leftPct}% + 2px);width:calc(${widthPct}% - 4px);`;
      }

      const value = {
        hourFrom,
        hourTo,
        hours,
        hourPx: HOUR_PX,
        height: (hourTo - hourFrom) * HOUR_PX,
        maxLanes: items.reduce((m, it) => Math.max(m, it.lanes), 1),
        items,
        unscheduled,
      };
      schedCache.src = this.calendar;
      schedCache.day = dayIso;
      schedCache.value = value;
      return value;
    },

    // Posición (px) de la línea de una hora dentro del lienzo del día
    hourTop(h) {
      const sch = this.daySchedule(this.selectedDay);
      return `${(h - sch.hourFrom) * sch.hourPx}px`;
    },

    // Ancho mínimo del lienzo: `CANAL_HORAS + carriles * LANE_MIN_PX`, con
    // un suelo de CAL_MIN_PX para días con pocos carriles. Como es un
    // min-width (no un width), el lienzo sigue creciendo hasta llenar el
    // panel cuando el panel es más ancho.
    schedMinWidth() {
      const lanes = this.daySchedule(this.selectedDay).maxLanes;
      return Math.max(CAL_MIN_PX, CANAL_HORAS + lanes * LANE_MIN_PX);
    },

    // ¿La tarjeta es demasiado angosta para leer el título en horizontal?
    // Con ROTATE_LANES o más carriles el ancho efectivo cae por debajo de
    // ~100 px y el título se truncaría a 4-5 caracteres; girado, el texto
    // aprovecha el ALTO de la tarjeta sin mover nada del eje de horas.
    isNarrow(item) {
      return !!item && Number(item.lanes) >= ROTATE_LANES;
    },

    // Qué variante pinta la plantilla. La angosta se rinde girada; al pasar
    // el cursor se sustituye por la ancha (que ya se está mostrando a 240 px
    // de ancho), de modo que el nombre completo aparece en horizontal.
    showNarrow(item) {
      return this.isNarrow(item) && !this.isHovered(item);
    },
    showWide(item) {
      return !this.isNarrow(item) || this.isHovered(item);
    },

    // Bloques de la ficha horizontal que solo aparecen si la tarjeta tiene
    // sitio (ver FULL_LOC_H / FULL_DEEP_H): la altura no la decide el
    // contenido sino el tramo de horas que ocupa.
    showLocRow(item) {
      return !!(item && item.geom && item.geom.height >= FULL_LOC_H);
    },
    showDeepRow(item) {
      return !!(item && item.geom && item.geom.height >= FULL_DEEP_H);
    },
    showReqRow(item) {
      return !!(item && item.geom && item.geom.height >= FULL_REQ_H);
    },

    // "A · B · C" con los nombres de los ponentes, sin grado ni organización
    speakersLine(item) {
      const raw = (item && item.activity && item.activity.speakers) || [];
      if (!Array.isArray(raw)) return "";
      return raw
        .map((s) => (typeof s === "string" ? s : (s && s.name) || ""))
        .map((s) => String(s).trim())
        .filter(Boolean)
        .join(" · ");
    },

    // --- Hover: tarjeta expandida (estilo Google Calendar) ------------------
    // El `title` nativo tarda ~1 s, no se estiliza y no sirve en táctil.
    // Aquí la tarjeta angosta se ensancha, sube de nivel y muestra su
    // contenido HORIZONTAL completo por encima de los vecinos. El clic ya
    // abre el modal, así que en móvil no hace falta nada más.
    hoverOn(item) {
      if (item) this.hoveredId = item.id;
    },
    hoverOff(item) {
      if (item && this.hoveredId === item.id) this.hoveredId = null;
    },
    isHovered(item) {
      return !!item && this.hoveredId === item.id;
    },

    // `style` de la tarjeta: la geometría calculada, con el ancho y el
    // z-index sustituidos si está bajo el cursor. Se recalcula en lugar de
    // añadir una clase con !important para no depender de la versión de
    // Tailwind ni de ganarle al `width` inline del atributo style.
    cardStyle(item) {
      const g = item && item.geom;
      if (!g) return (item && item.style) || "";
      const hover = this.isHovered(item);
      const width = hover ? `${HOVER_W}px` : `calc(${g.widthPct}% - 4px)`;
      const z = hover ? ";z-index:40" : "";
      return (
        `top:${g.top}px;height:${g.height}px;` +
        `left:calc(${g.leftPct}% + 2px);width:${width}${z};`
      );
    },

    // Nivel de detalle de la tira girada, por DURACIÓN de la sesión (no por
    // píxeles): así no depende ni del zoom del eje ni del viewport.
    //   < 4 h  → nombre · horario
    //   ≥ 4 h  → nombre · horario · ubicación · cupo · sesión
    schedTier(item) {
      const a = (item && item.activity) || {};
      const s = this._toMin(a.starts_at);
      let e = this._toMin(a.ends_at);
      if (s == null) return 0;
      if (e == null || e <= s) e = s + 60;
      return (e - s) / 60 >= TIER_FULL_HOURS ? 1 : 0;
    },

    // Texto de la tarjeta girada, que se lee de abajo hacia arriba. El
    // nombre va PRIMERO: en un timeline la posición ya dice a qué hora es,
    // y en una tarjeta de 1 h la hora delantera se comía los 12 caracteres
    // de los que solo 16 eran ella misma, de modo que el nombre no llegó a
    // empezar. Al ser el resto un sufijo, una tarjeta que crece solo añade
    // por la derecha: las tiras son prefijos unas de otras.
    schedText(item) {
      if (!item) return "";
      const a = item.activity || {};
      const parts = [];
      if (a.name) parts.push(a.name);
      parts.push(`${a.starts_at || "—"} – ${a.ends_at || "—"}`);
      if (this.schedTier(item) >= 1) {
        if (a.location) parts.push(a.location);
        const cupo = this.cupoLabel(a);
        if (cupo) parts.push(cupo);
        if ((a.session_total || 1) > 1) {
          parts.push(`Sesión ${a.session_index}/${a.session_total}`);
        }
      }
      return parts.filter(Boolean).join(" · ");
    },

    // --- Día activo en el índice sticky ------------------------------------
    // En admin los días son COLUMNAS lado a lado y todas están visibles a la
    // vez, así que no hay "sección actual" vertical que resaltar (a diferencia
    // de la vista del estudiante). Lo que sí tiene sentido —y solo cuando las
    // columnas NO caben, es decir en móvil— es pintar de indigo la píldora del
    // día cuya columna está a la vista mientras hacemos scroll horizontal.

    calScroller() {
      if (typeof document === "undefined") return null;
      const el = document.querySelector("[data-cal-scroll]");
      return el && typeof el.getBoundingClientRect === "function" ? el : null;
    },

    updateActiveDay() {
      // En modo "horario" no hay columnas: el día resaltado lo manda
      // selectedDay, no el scroll horizontal.
      if (this.viewMode !== "range") return;
      const days = (this.calendar && this.calendar.days) || [];
      const scroller = this.calScroller();
      if (days.length < 2 || !scroller) {
        this.activeDay = null;
        return;
      }
      // Sin overflow horizontal (escritorio): todas las columnas caben,
      // no hay columna "actual" y no se resalta ninguna.
      if (scroller.scrollWidth - scroller.clientWidth <= 1) {
        this.activeDay = null;
        return;
      }
      const cr = scroller.getBoundingClientRect();
      let best = null;
      let bestVisible = 0;
      for (const d of days) {
        const el = document.getElementById(`cal-day-${d}`);
        if (!el || typeof el.getBoundingClientRect !== "function") continue;
        const r = el.getBoundingClientRect();
        const visible = Math.min(r.right, cr.right) - Math.max(r.left, cr.left);
        if (visible > bestVisible) {
          bestVisible = visible;
          best = d;
        }
      }
      this.activeDay = best;
    },

    initDaySpy() {
      if (typeof window === "undefined" || this._spyHandler) return;
      const schedule =
        typeof window.requestAnimationFrame === "function"
          ? (fn) => window.requestAnimationFrame(fn)
          : (fn) => setTimeout(fn, 16);
      this._spyHandler = () => {
        if (this._spyRaf) return;
        this._spyRaf = schedule(() => {
          this._spyRaf = null;
          this.updateActiveDay();
        });
      };
      this._spyUnload = () => this.destroyDaySpy();
      // El scroll horizontal vive en el contenedor, no en window (el evento
      // "scroll" no burbujea, hay que escuchar en el propio elemento)
      this._spyScroller = this.calScroller();
      if (this._spyScroller) {
        this._spyScroller.addEventListener("scroll", this._spyHandler, {
          passive: true,
        });
      }
      window.addEventListener("resize", this._spyHandler);
      // Limpieza best-effort al salir (mismo criterio que registrations.js)
      window.addEventListener("beforeunload", this._spyUnload);
      this.updateActiveDay();
    },

    destroyDaySpy() {
      if (typeof window === "undefined" || !this._spyHandler) return;
      if (this._spyScroller) {
        this._spyScroller.removeEventListener("scroll", this._spyHandler);
      }
      window.removeEventListener("resize", this._spyHandler);
      window.removeEventListener("beforeunload", this._spyUnload);
      if (this._spyRaf && typeof window.cancelAnimationFrame === "function") {
        window.cancelAnimationFrame(this._spyRaf);
      }
      this._spyRaf = null;
      this._spyHandler = null;
      this._spyUnload = null;
      this._spyScroller = null;
    },

    // Modal de detalle
    openDetail(activity) {
      this.selectedActivity = activity;
      this.showDetail = true;
    },
    closeDetail() {
      this.showDetail = false;
      this.selectedActivity = null;
    },
  };
}

// Exponer globalmente para Alpine (x-data="calendarAdmin()")
if (typeof window !== "undefined") {
  window.calendarAdmin = calendarAdmin;
}

// Exportar para Node/Jest (CommonJS)
if (typeof module !== "undefined" && module.exports) {
  module.exports = calendarAdmin;
}
