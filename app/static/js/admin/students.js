// static/js/admin/students.js
function studentsAdmin() {
  return {
    // Estado
    students: [],
    loading: false,
    errorMessage: "",

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
      event_id: null,
      activity_id: null,
      career: "",
    },

    // Para los selectores de filtros
    events: [],
    activities: [],
    allActivities: [],
    careers: [],

    // Modal de detalle del estudiante
    showDetailModal: false,
    currentStudent: null,
    studentEventsHours: [],
    loadingDetail: false,

    // Modal de detalle de evento específico
    showEventDetailModal: false,
    currentEventDetail: null,
    eventActivities: [],
    loadingEventDetail: false,

    // Modal de exportación de créditos complementarios (multi-evento)
    showExportModal: false,
    exportFilters: {
      event_ids: [],
      career: "",
    },
    exportData: [],
    loadingExport: false,
    exportError: "",
    // Metadatos de la última búsqueda (desglose por evento + omitidos)
    exportStats: {
      events: [],
      excluded_already_credited: 0,
      excluded_by_override: 0,
      excluded_already_granted: 0,
    },
    // Vista: añade a la lista a los excluidos por ya tener eventos gastados
    // (marca already_granted). Solo afecta a la vista previa en pantalla:
    // el Excel y el otorgamiento nunca lo activan.
    includeGranted: false,
    granting: false,
    exportingExcel: false,
    // false = migración 20261002_add_credit_grants pendiente: no se puede
    // registrar un otorgamiento, así que el botón queda bloqueado.
    creditGrantsAvailable: true,
    // Overrides manuales de crédito (tabla credit_overrides)
    creditOverrides: [],
    overrideSearch: "",
    overrideSearchResult: null,
    overrideSearchError: "",
    searchingOverride: false,
    // Sincronización desde API externa
    syncingStudents: false,

    // Inicialización
    async init() {
      // Lazy-init (Fase D): diferir cargas hasta la pestaña "students"
      await window.tabLazyBoot("students", async () => {
        await this.loadEvents();
        await this.loadAllActivities();
        await this.loadStudents(1);
      });
    },

    // Cargar estudiantes con filtros
    async loadStudents(page = 1) {
      this.loading = true;
      this.errorMessage = "";

      try {
        const params = new URLSearchParams({
          page: page,
          per_page: 10,
        });

        if (this.filters.search) {
          params.append("search", this.filters.search);
        }
        if (this.filters.event_id) {
          params.append("event_id", this.filters.event_id);
        }
        if (this.filters.activity_id) {
          params.append("activity_id", this.filters.activity_id);
        }
        if (this.filters.career) {
          params.append("career", this.filters.career);
        }

        const response = await fetch(`/api/students?${params}`, {
          headers: window.getAuthHeaders(),
        });

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(`Error: ${response.status}`);
        }

        const data = await response.json();
        this.students = data.students || [];

        this.pagination = {
          current_page: data.current_page || 1,
          last_page: data.pages || 1,
          total: data.total || 0,
          from: this.students.length > 0 ? (data.current_page - 1) * 10 + 1 : 0,
          to: Math.min(data.current_page * 10, data.total || 0),
          pages: Array.from({ length: data.pages || 1 }, (_, i) => i + 1),
        };
      } catch (error) {
        console.error("Error loading students:", error);
        this.errorMessage = "Error al cargar estudiantes";
        window.showToast && window.showToast(this.errorMessage, "error");
      } finally {
        this.loading = false;
      }
    },

    // Cargar eventos para el filtro
    async loadEvents() {
      try {
        const response = await fetch("/api/events", {
          headers: window.getAuthHeaders(),
        });

        if (response.ok) {
          const data = await response.json();
          this.events = data.events || [];
        }
      } catch (error) {
        console.error("Error loading events:", error);
      }
    },

    // Cargar todas las actividades
    async loadAllActivities() {
      try {
        const response = await fetch("/api/activities?per_page=1000", {
          headers: window.getAuthHeaders(),
        });

        if (response.ok) {
          const data = await response.json();
          this.allActivities = data.activities || [];
          this.updateActivitiesFilter();
        }
      } catch (error) {
        console.error("Error loading activities:", error);
      }
    },

    // Actualizar actividades según evento seleccionado
    updateActivitiesFilter() {
      if (this.filters.event_id) {
        this.activities = this.allActivities.filter(
          (a) => a.event_id === parseInt(this.filters.event_id),
        );
      } else {
        this.activities = this.allActivities;
      }

      // Reset activity filter if not in filtered list
      if (this.filters.activity_id) {
        const exists = this.activities.find(
          (a) => a.id === parseInt(this.filters.activity_id),
        );
        if (!exists) {
          this.filters.activity_id = null;
        }
      }
    },

    // Aplicar filtros
    applyFilters() {
      this.updateActivitiesFilter();
      this.loadStudents(1);
    },

    // Limpiar filtros
    clearFilters() {
      this.filters = {
        search: "",
        event_id: null,
        activity_id: null,
        career: "",
      };
      this.activities = this.allActivities;
      this.loadStudents(1);
    },

    // Cambiar página
    changePage(page) {
      if (page >= 1 && page <= this.pagination.last_page) {
        this.loadStudents(page);
      }
    },

    // Ver detalle de estudiante
    async viewStudentDetail(student) {
      this.currentStudent = { ...student };
      this.studentEventsHours = [];
      this.showDetailModal = true;
      this.loadingDetail = true;

      try {
        const response = await fetch(
          `/api/students/${student.id}/hours-by-event`,
          {
            headers: window.getAuthHeaders(),
          },
        );

        if (!response.ok) {
          throw new Error(`Error: ${response.status}`);
        }

        const data = await response.json();
        this.studentEventsHours = data.events_hours || [];
      } catch (error) {
        console.error("Error loading student details:", error);
        window.showToast &&
          window.showToast("Error al cargar detalles", "error");
      } finally {
        this.loadingDetail = false;
      }
    },

    // Cerrar modal de detalle
    closeDetailModal() {
      this.showDetailModal = false;
      this.currentStudent = null;
      this.studentEventsHours = [];
    },

    // Pedir impersonación: el modal compartido (admin/base.html) escucha el
    // evento 'impersonate:request' y realiza el POST + apertura de pestaña.
    requestImpersonation(student) {
      if (!student || !student.id) return;
      window.dispatchEvent(
        new CustomEvent("impersonate:request", { detail: { student } }),
      );
    },

    // Ver detalle de evento específico
    async viewEventDetail(eventData) {
      if (!this.currentStudent) return;

      this.currentEventDetail = { ...eventData };
      this.eventActivities = [];
      this.showEventDetailModal = true;
      this.loadingEventDetail = true;

      try {
        const response = await fetch(
          `/api/students/${this.currentStudent.id}/event/${eventData.event_id}/details`,
          {
            headers: window.getAuthHeaders(),
          },
        );

        if (!response.ok) {
          throw new Error(`Error: ${response.status}`);
        }

        const data = await response.json();
        this.eventActivities = data.activities || [];
        this.currentEventDetail.total_confirmed_hours =
          data.total_confirmed_hours;
        this.currentEventDetail.has_complementary_credit =
          data.has_complementary_credit;
      } catch (error) {
        console.error("Error loading event details:", error);
        window.showToast &&
          window.showToast("Error al cargar actividades", "error");
      } finally {
        this.loadingEventDetail = false;
      }
    },

    // Sincronizar estudiantes desde API externa hacia la BD local.
    // Esto es una acción explícita del admin: no forma parte del flujo de
    // subida batch (la subida ya consultará el API cuando sea necesario).
    async syncStudentsFromAPI() {
      if (
        !confirm(
          "¿Deseas sincronizar estudiantes desde la API externa? Esto puede crear/actualizar muchos registros.",
        )
      )
        return;
      this.syncingStudents = true;
      try {
        const res = await fetch(`/api/students/sync-external`, {
          method: "POST",
          headers: window.getAuthHeaders({
            "Content-Type": "application/json",
          }),
          body: JSON.stringify({}),
        });
        if (!res.ok) {
          const txt = await res.text().catch(() => "");
          throw new Error(`Error: ${res.status} ${txt}`);
        }
        const body = await res.json().catch(() => ({}));
        const created = body.created || 0;
        const updated = body.updated || 0;
        window.showToast &&
          window.showToast(
            `Sincronización completada. Creados: ${created}, Actualizados: ${updated}`,
            "success",
          );
        // refrescar la lista de estudiantes para ver los cambios
        await this.loadStudents(1);
      } catch (err) {
        console.error("syncStudentsFromAPI error", err);
        window.showToast &&
          window.showToast("Error al sincronizar estudiantes", "error");
      } finally {
        this.syncingStudents = false;
      }
    },

    // Cerrar modal de detalle de evento
    closeEventDetailModal() {
      this.showEventDetailModal = false;
      this.currentEventDetail = null;
      this.eventActivities = [];
    },

    // Formatear fecha (canónico corto: "15 ene 2024")
    formatDate(dateString) {
      if (!dateString) return "Sin fecha";
      try {
        const dh = window.dateHelpers;
        if (dh && typeof dh.formatDateShort === "function") {
          const out = dh.formatDateShort(dateString);
          if (out && out !== "Sin fecha") return out;
        }
      } catch (e) {
        // fallback manual abajo
      }
      const date = new Date(dateString);
      if (isNaN(date)) return "Sin fecha";
      return date.toLocaleDateString("es-MX", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    },

    // Formatear fecha y hora (canónico corto, 24 h)
    formatDateTime(dateString) {
      if (!dateString) return "Sin fecha";
      try {
        const dh = window.dateHelpers;
        if (dh && typeof dh.formatDateTimeShort === "function") {
          const out = dh.formatDateTimeShort(dateString);
          if (out && out !== "Sin fecha") return out;
        }
      } catch (e) {
        // fallback manual abajo
      }
      const date = new Date(dateString);
      if (isNaN(date)) return "Sin fecha";
      return date.toLocaleString("es-MX", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
      });
    },

    // Obtener clase de badge de status
    getStatusBadgeClass(status) {
      const classes = {
        Registrado: "bg-yellow-100 text-yellow-800",
        Confirmado: "bg-blue-100 text-blue-800",
        Asistió: "bg-green-100 text-green-800",
        Ausente: "bg-red-100 text-red-800",
        Cancelado: "bg-gray-100 text-gray-800",
      };
      return classes[status] || "bg-gray-100 text-gray-800";
    },

    // Abrir modal de exportación de créditos (multi-evento)
    async openExportModal() {
      this.showExportModal = true;
      this.exportFilters = {
        event_ids: this.filters.event_id ? [this.filters.event_id] : [],
        career: this.filters.career || "",
      };
      this.resetExportResults();
      this.overrideSearch = "";
      this.overrideSearchResult = null;
      this.overrideSearchError = "";
      await this.loadCreditOverrides();
    },

    // Cerrar modal de exportación
    closeExportModal() {
      this.showExportModal = false;
      this.exportData = [];
      this.exportError = "";
      this.exportStats = {
        events: [],
        excluded_already_credited: 0,
        excluded_by_override: 0,
        excluded_already_granted: 0,
      };
      this.includeGranted = false;
      this.creditOverrides = [];
    },

    // Limpiar resultados de la búsqueda actual
    resetExportResults() {
      this.exportData = [];
      this.exportError = "";
      this.exportStats = {
        events: [],
        excluded_already_credited: 0,
        excluded_by_override: 0,
        excluded_already_granted: 0,
      };
    },

    // Alternar la vista de ya otorgados (auditoría) y volver a buscar
    async toggleIncludeGranted() {
      await this.loadComplementaryCredits();
    },

    // Pendientes de otorgar: excluye a los que ya están acreditados cuando
    // la vista de auditoría los añade a la tabla.
    pendingGrantCount() {
      return (this.exportData || []).filter((s) => !s.already_granted).length;
    },

    // Agregar/quitar un evento de la selección multi-evento
    toggleExportEvent(eventId) {
      const ids = this.exportFilters.event_ids || [];
      const idx = ids.indexOf(eventId);
      if (idx >= 0) {
        ids.splice(idx, 1);
      } else {
        ids.push(eventId);
      }
      this.exportFilters.event_ids = ids;
      this.resetExportResults();
    },

    // Horas de un estudiante en un evento del desglose (para la tabla)
    hoursInEvent(student, eventId) {
      const hours =
        student && student.hours_by_event
          ? student.hours_by_event[eventId]
          : null;
      return (hours || 0).toFixed(1);
    },

    // Cargar estudiantes con crédito complementario (horas combinadas)
    async loadComplementaryCredits() {
      if (
        !this.exportFilters.event_ids ||
        this.exportFilters.event_ids.length === 0
      ) {
        this.exportError = "Debe seleccionar al menos un evento";
        return;
      }

      this.loadingExport = true;
      this.exportError = "";

      try {
        const params = new URLSearchParams();
        params.append("event_ids", this.exportFilters.event_ids.join(","));

        if (this.exportFilters.career) {
          params.append("career", this.exportFilters.career);
        }
        if (this.includeGranted) {
          params.append("include_granted", "1");
        }

        const response = await fetch(
          `/api/students/complementary-credits?${params}`,
          {
            headers: window.getAuthHeaders(),
          },
        );

        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(`Error: ${response.status}`);
        }

        const data = await response.json();
        this.exportData = data.students || [];
        this.creditGrantsAvailable = data.credit_grants_available !== false;
        this.exportStats = {
          events: data.events || [],
          excluded_already_credited: data.excluded_already_credited || 0,
          excluded_by_override: data.excluded_by_override || 0,
          excluded_already_granted: data.excluded_already_granted || 0,
        };
      } catch (error) {
        console.error("Error loading complementary credits:", error);
        this.exportError = "Error al cargar estudiantes con créditos";
        window.showToast && window.showToast(this.exportError, "error");
      } finally {
        this.loadingExport = false;
      }
    },

    // Parámetros de la última búsqueda (lista, Excel y otorgamiento
    // comparten el mismo set de filtros para que calculen lo mismo)
    buildCreditsParams() {
      const params = new URLSearchParams();
      params.append("event_ids", this.exportFilters.event_ids.join(","));
      if (this.exportFilters.career) {
        params.append("career", this.exportFilters.career);
      }
      return params;
    },

    // Descarga el XLSX de créditos. La ruta exige header Authorization, así
    // que no basta window.open (la pestaña abriría la URL sin token y el
    // backend responde 401): se consume con fetch autenticado y se sirve
    // como blob, mismo patrón que reports.js.
    async downloadCreditsExcel(params) {
      const f =
        typeof window.safeFetch === "function" ? window.safeFetch : fetch;
      const res = await f(
        `/api/students/complementary-credits/export?${params}`,
      );
      if (!res) {
        throw new Error("sin respuesta del servidor");
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || `Error: ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const cd = res.headers.get("Content-Disposition") || "";
      const m = cd.match(/filename="?(.*?)"?$/);
      a.download = m && m[1] ? m[1] : `creditos_${Date.now()}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    },

    // Exportar a Excel (mismos filtros multi-evento que la lista)
    async exportToExcel() {
      if (
        !this.exportFilters.event_ids ||
        this.exportFilters.event_ids.length === 0
      ) {
        window.showToast &&
          window.showToast("Debe seleccionar al menos un evento", "error");
        return;
      }

      this.exportingExcel = true;
      try {
        await this.downloadCreditsExcel(this.buildCreditsParams());
        window.showToast && window.showToast("Descarga iniciada", "success");
      } catch (error) {
        console.error("Error exporting to Excel:", error);
        window.showToast &&
          window.showToast(error.message || "Error al exportar", "error");
      } finally {
        this.exportingExcel = false;
      }
    },

    // Otorga el crédito complementario (Fase 3, tabla credit_grants).
    // Orden deliberado: primero el archivo, después el registro. Si el
    // registro falla no se gastó ningún evento y se puede reintentar sin
    // doble acreditación; al revés, el crédito quedaría gastado sin archivo.
    async grantCredits() {
      if (this.creditGrantsAvailable === false) {
        window.showToast &&
          window.showToast(
            "No se puede otorgar: falta aplicar la migración " +
              "20261002_add_credit_grants (flask db upgrade)",
            "error",
          );
        return;
      }

      if (
        !this.exportFilters.event_ids ||
        this.exportFilters.event_ids.length === 0
      ) {
        window.showToast &&
          window.showToast("Debe seleccionar al menos un evento", "error");
        return;
      }

      const pending = (this.exportData || []).filter(
        (s) => !s.already_granted,
      ).length;
      if (pending === 0) {
        window.showToast &&
          window.showToast(
            "No hay estudiantes pendientes de acreditación",
            "error",
          );
        return;
      }

      const confirmed = window.confirm(
        `¿Otorgar el crédito complementario a ${pending} estudiante(s)?\n\n` +
          "Se descargará el Excel para subirlo a la plataforma externa y los " +
          "eventos usados quedarán marcados como acreditados: ya no podrán " +
          "volver a usarse para acumular horas en una acreditación futura.",
      );
      if (!confirmed) return;

      this.granting = true;
      let downloaded = false;
      try {
        // 1) Archivo primero: si falla aquí no se registró nada.
        await this.downloadCreditsExcel(this.buildCreditsParams());
        downloaded = true;

        // 2) Registrar el lote con los mismos parámetros.
        const res = await fetch("/api/students/credit-grants", {
          method: "POST",
          headers: window.getAuthHeaders(),
          body: JSON.stringify({
            event_ids: this.exportFilters.event_ids,
            career: this.exportFilters.career || "",
            confirm: true,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data.message || `Error: ${res.status}`);
        }

        window.showToast &&
          window.showToast(
            `Crédito otorgado a ${data.granted_students} estudiante(s): ` +
              `${data.granted_events} evento(s) marcados como acreditados`,
            "success",
          );
      } catch (error) {
        console.error("Error granting credits:", error);
        const detail = downloaded
          ? `El archivo se descargó pero no se registró el otorgamiento ` +
            `(${error.message}). Reintenta: nadie quedó acreditado dos veces.`
          : `No se descargó el archivo (${error.message}); no se registró ` +
            `nada. Reintenta.`;
        window.showToast && window.showToast(detail, "error");
      } finally {
        this.granting = false;
        // Refresca la lista: si el registro salió bien, los acreditados
        // pasan a "ya otorgados" y desaparecen de los pendientes.
        await this.loadComplementaryCredits();
      }
    },

    // ---- Overrides manuales de crédito (credit_overrides) ----

    // Cargar overrides existentes (no bloquea el modal si la tabla no existe)
    async loadCreditOverrides() {
      try {
        const response = await fetch("/api/students/credit-overrides", {
          headers: window.getAuthHeaders(),
        });
        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(`Error: ${response.status}`);
        }
        const data = await response.json();
        this.creditOverrides = data.overrides || [];
      } catch (error) {
        // Puede fallar si la migración 20261001 aún no corrió: el modal
        // sigue funcionando sin overrides en lugar de bloquearse.
        console.warn("Overrides no disponibles:", error);
        this.creditOverrides = [];
      }
    },

    // ¿El estudiante tiene override manual?
    hasCreditOverride(studentId) {
      return (this.creditOverrides || []).some(
        (o) => o.student_id === studentId,
      );
    },

    // Crear/actualizar override (include|exclude) y refrescar lista + overrides
    async setCreditOverride(studentId, decision) {
      try {
        const response = await fetch("/api/students/credit-overrides", {
          method: "POST",
          headers: window.getAuthHeaders(),
          body: JSON.stringify({ student_id: studentId, decision }),
        });
        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(`Error: ${response.status}`);
        }
        window.showToast && window.showToast("Override guardado", "success");
        await this.loadCreditOverrides();
        await this.loadComplementaryCredits();
      } catch (error) {
        console.error("Error saving override:", error);
        window.showToast &&
          window.showToast("Error al guardar override", "error");
      }
    },

    // Eliminar override y refrescar lista + overrides
    async removeCreditOverride(studentId) {
      try {
        const response = await fetch(
          `/api/students/credit-overrides/${studentId}`,
          { method: "DELETE", headers: window.getAuthHeaders() },
        );
        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(`Error: ${response.status}`);
        }
        window.showToast && window.showToast("Override eliminado", "success");
        await this.loadCreditOverrides();
        await this.loadComplementaryCredits();
      } catch (error) {
        console.error("Error deleting override:", error);
        window.showToast &&
          window.showToast("Error al eliminar override", "error");
      }
    },

    // Buscar estudiante (por control o nombre) para forzar su inclusión
    async searchOverrideStudent() {
      const query = (this.overrideSearch || "").trim();
      if (!query) {
        this.overrideSearchError = "Escribe un número de control o nombre";
        return;
      }
      this.searchingOverride = true;
      this.overrideSearchError = "";
      this.overrideSearchResult = null;
      try {
        const params = new URLSearchParams({ search: query, per_page: 10 });
        const response = await fetch(`/api/students?${params}`, {
          headers: window.getAuthHeaders(),
        });
        if (!response.ok) {
          if (response.status === 401) {
            this.redirectToLogin();
            return;
          }
          throw new Error(`Error: ${response.status}`);
        }
        const data = await response.json();
        const list = data.students || [];
        if (list.length === 0) {
          this.overrideSearchError = "Sin resultados";
          return;
        }
        // Preferir coincidencia exacta de número de control
        const exact = list.find(
          (s) => String(s.control_number).toLowerCase() === query.toLowerCase(),
        );
        this.overrideSearchResult = exact || list[0];
      } catch (error) {
        console.error("Error searching student:", error);
        this.overrideSearchError = "Error al buscar estudiante";
        window.showToast && window.showToast(this.overrideSearchError, "error");
      } finally {
        this.searchingOverride = false;
      }
    },

    // Forzar inclusión del estudiante encontrado en la búsqueda
    async includeOverrideFromSearch() {
      if (!this.overrideSearchResult) return;
      const studentId = this.overrideSearchResult.id;
      this.overrideSearch = "";
      this.overrideSearchResult = null;
      await this.setCreditOverride(studentId, "include");
    },

    // Redireccionar al login
    redirectToLogin() {
      localStorage.removeItem("authToken");
      localStorage.removeItem("userType");
      window.location.href = "/";
    },
  };
}

// Hacer la función globalmente disponible
if (typeof window !== "undefined") {
  window.studentsAdmin = studentsAdmin;
}

// Para compatibilidad con Node (tests)
if (typeof module !== "undefined" && module.exports) {
  module.exports = studentsAdmin;
}
