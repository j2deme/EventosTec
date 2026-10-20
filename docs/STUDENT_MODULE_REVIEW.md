# Plan de revisión y corrección — Módulo del estudiante

> **Cómo usar este documento**
> Es un plan vivo. Cada ítem tiene su casilla: se marca `[x]` cuando se commitea, con el
> hash en la tabla de _Registro de avance_ al final. Si un ítem cambia de alcance, se
> anota en _Historial de decisiones_.
>
> **Los números de línea corresponden al HEAD `b92fc09`.** Se re-buscan tras cada commit.

---

## 0. Decisiones tomadas

| #   | Decisión                                                                                                                                                                                      | Tomada el  |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| D-1 | **Fase B3**: endpoint dedicado de búsqueda de estudiante. No combinar funcionalidades: así controlamos qué información se envía y se recibe.                                                  | 2026-10-05 |
| D-2 | **Fase E**: **habilitar** los filtros (no eliminarlos). En el evento activo hay 45 actividades; el año pasado hubo más de 60 y de muchos tipos, así que filtrar por tipo ayuda al estudiante. | 2026-10-05 |
| D-3 | **Orden**: atacar la **Fase A** primero.                                                                                                                                                      | 2026-10-05 |
| D-4 | Prioridad rectora: **que nada se rompa en producción** → fases cortas, un commit por ítem, verificación por ítem.                                                                             | 2026-10-05 |

---

## 1. Hallazgos verificados

### 1.1 Crítico (detectado al preparar la Fase B)

**`GET /api/students/?search=<texto>` está SIN autenticación y devuelve los registros de
asistencia de los estudiantes.**

- `app/api/students_bp.py:24` — `get_students()` no lleva `@jwt_required()` y la app no
  tiene ningún `before_request` global (verificado: 0 coincidencias en `app/`).
- Devuelve `students_schema.dump(...)`, y `app/schemas/student_schema.py:22-23` incluye
  `registrations` y `attendances` como `fields.Nested(..., many=True)`. Verificado en
  runtime contra el schema:

```text
student_schema.fields = ['attendances', 'career', 'control_number', 'created_at',
                         'email', 'full_name', 'id', 'registrations', 'updated_at']
registrations         = ['activity', 'activity_id', 'attended', 'confirmation_date',
                         'created_at', 'id', 'registration_date', 'status',
                         'student', 'student_id', 'updated_at']
attendances           = ['activity_id', 'attendance_percentage', 'check_in_time',
                         'check_out_time', 'created_at', 'id', 'is_paused',
                         'pause_time', 'resume_time', 'status', 'student_id', 'updated_at']
```

- **Impacto**: sin token, enumerando por número de control o por nombre, se obtiene quién
  se preregistró a qué actividad, con qué estado, y sus horas de entrada/salida.
- **Por qué no se tapó antes**: la preregistración pública lo necesita
  (`public/registrations_public.js:701`) y el walk-in de staff también
  (`public/staff_walkin.html:217`). Por eso la solución no es "poner JWT" a ciegas
  (rompería el alta pública), sino el **D-1: endpoint dedicado**.

### 1.2 Altos

| ID   | Hallazgo                                                                                                                                                                                                                                                              | Sitio                          |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| A-0  | Se usa la API de **Alpine 2** (`el.__x` / `getUnobservedData`) con **Alpine 3**. Verificado descargando el bundle de `alpinejs@3.x.x` que sirve `base.html`: no contiene `__x` ni `getUnobservedData` (sí `_x_dataStack`). 11 call sites.                             | 5 archivos, fase A             |
| A-0b | **Botón "Explorar eventos" muerto** (estado vacío de _Mis Preregistros_): `registrations.js:270` no tiene ningún fallback.                                                                                                                                            | `registrations.html:325`       |
| A-0c | **`refreshTabContent` es código muerto**: al volver a Eventos/Histórico/Actividades los datos no se refrescan (listas viejas).                                                                                                                                        | `dashboard.js:243-310,471-496` |
| C-0  | **XSS + handler filtrado** en el modal multidía: `activity.name` se inyecta con `insertAdjacentHTML` sin escapar; `document.onkeydown` se asigna y nunca se libera; el guard `inflight` entra después de abrir el modal (doble clic ⇒ dos modales con el mismo `id`). | `event_activities.js:824-912`  |

### 1.3 Medios

| ID  | Hallazgo                                                                                                                                                                                    | Sitio                            |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| B-1 | `GET /api/students/<id>/hours-by-event` y `GET /api/students/<id>/event/<id>/details` sin `@jwt_required()`.                                                                                | `students_bp.py:308,392`         |
| B-2 | **IDOR** en `GET /api/registrations/`: acepta cualquier `student_id` con solo tener token. El POST del mismo archivo sí lo restringe (línea 38-47).                                         | `registrations_bp.py:150-160`    |
| D-1 | Sin estado "enviando" en cancelar/reactivar ⇒ doble clic = dos `DELETE`; el segundo pisa el toast de éxito con uno de error.                                                                | `registrations.js:189,229`       |
| D-2 | `from`/`to` calculados con un **`20` fijo** ignorando `data.from`/`data.to` que el backend ya devuelve. Hoy invisible porque `per_page=2000` ⇒ 1 página.                                    | `event_activities.js:263-264`    |
| D-3 | `canRegisterForActivity` usa `!== null` y `availabilityCode` usa `!= null` ⇒ si falta `max_capacity`, la tarjeta dice "Disponible" y el botón sale deshabilitado.                           | `event_activities.js:701` vs 762 |
| D-4 | Rutas declaradas con `/` pero llamadas sin la barra final ⇒ un `308` por petición.                                                                                                          | 4 sitios (ver B/D4)              |
| E-1 | `sort` del backend **solo soporta `name:asc\|desc`**; cualquier otra clave cae a `created_at desc`. El cliente envía `start_datetime:asc` por defecto ⇒ **el orden por fecha no funciona**. | `activities_bp.py:142-160`       |
| E-2 | El `activity_type` se filtra dos veces (líneas 79 y 131) y el parámetro `type` (línea 77) se pisa inmediatamente ⇒ parámetro muerto (nadie lo usa, verificado).                             | `activities_bp.py:77-79,131`     |

### 1.4 Menores / mantenibilidad

| ID  | Hallazgo                                                                                                                                                                                                                   | Sitio                               |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| F-1 | `redirectToLogin` duplicado ×7; 6 idénticas y `history.js` se omite `removeItem("studentProfile")` ⇒ caché de perfil obsoleto tras un 401.                                                                                 | 7 archivos                          |
| F-2 | `getCurrentStudentId` ×4 con semánticas distintas: `history.js` acepta `studentProfile` + `sub\|user_id\|id`; `event_activities` y `registrations` solo `sub`.                                                             | 4 archivos                          |
| F-3 | Formateadores de fecha/hora duplicados en 6 archivos pese a `dateHelpers.js` ya cargado.                                                                                                                                   | 6 archivos                          |
| F-4 | `viewEventDetails` duplicado.                                                                                                                                                                                              | `dashboard.js:382`, `events.js:154` |
| F-5 | Los `<script>` de las 6 pestañas están dentro del bloque `content`, es decir, se ejecutan antes de `dateHelpers.js` y `app.js`. Además `event_activities.js` cuelga de `dashboard.html:44` y los otros 5 de sus parciales. | 7 plantillas                        |
| F-6 | A11y: solo `event_activities.html:578` tiene `@keydown.escape`; ningún modal tiene `role="dialog"`/`aria-modal`/foco inicial; botones de solo icono sin `aria-label`.                                                      | 4 plantillas                        |
| G-0 | 7 archivos JS (~3 400 líneas) con 3 archivos de test; nada cubre navegación, registro ni cancelación — A-0 no lo detectaría ningún test.                                                                                   | `student/__tests__/`                |
| P-1 | `per_page=2000` y `admin/reports.js:367` usa `per_page=1000` sobre un schema con relaciones anidadas ⇒ payload enorme y N+1.                                                                                               | `students_bp.py:78`                 |

### 1.5 Lo que está bien (no tocar)

Guard `inflight` del preregistro · sincronización de pestañas vía CustomEvent/localStorage/BroadcastChannel · lazy-init de pestañas (`tabLazyBoot`) · agrupación por día con `dateKey` local sin off-by-one · `logout` ya delegado en `window.logout` (`dashboard.js:452`) · `student_id` siempre del JWT · sin `console.log` residuales · sin `x-html` · `POST /api/registrations/` ya impide preregistrar a otros (línea 38-47) · los modales tienen `style="display:none"` (no hay FOUC) · `for_student=true` filtra `Magistral` también en backend.

---

## 2. Protocolo de verificación (aplica a todo)

| Momento                     | Comando                                                    | Umbral                                 |
| --------------------------- | ---------------------------------------------------------- | -------------------------------------- |
| Baseline, antes de empezar  | `npx jest --colors --runInBand`                            | 24 suites / 336 tests                  |
| Tras cada ítem JS           | `node --check <archivo>` y `npx prettier --check …`        | 0 fallos                               |
| Tras cada ítem de plantilla | `npx prettier --check <html>`                              | 0 fallos                               |
| Si se toca `.py`            | `venv/Scripts/python.exe -m pytest -q`                     | **requiere aprobación**                |
| Cierre de fase              | `npx jest --colors --runInBand` + `git status --porcelain` | sin regresiones, sin archivos colgando |

- **Un commit por ítem.** Nunca `git add -A`; staging explícito.
- `--no-verify` en cada commit (el hook `.git/hooks/pre-commit` no es ejecutable desde
  WSL: terminadores CRLF + `INSTALL_PYTHON` con ruta Windows). Sus comprobaciones se
  corren a mano: `prettier --check` sí, `ruff` solo si hay `.py`.
- Sin `push`. Sin stagear `.env`, `*.sql`, `instance/`, `venv/`, `app/static/img/`, `*.xlsx`.

---

## 3. Fase A — Navegación y refresco (Alpine 2 → 3) ← primero

### A1 · Helper único de componente y navegación

- [ ] **A1** — Archivo: `app/static/js/student/dashboard.js`, a nivel de módulo, junto a
      `window.tabLazyBoot`. Añadir:

```js
function getAlpineData(selector) {
  const el = document.querySelector(selector);
  if (!el) return null;
  if (window.Alpine && typeof window.Alpine.$data === "function") {
    try {
      return window.Alpine.$data(el);
    } catch (e) {
      /* aún no inicializado */
    }
  }
  return (el._x_dataStack && el._x_dataStack[0]) || null;
}
window.getAlpineData = getAlpineData;

function setStudentTab(tabId) {
  const data = getAlpineData('[x-data*="studentDashboard"]');
  if (data && typeof data.setActiveTab === "function") {
    data.setActiveTab(tabId);
    return true;
  }
  // Último recurso: dashboard.js escucha hashchange
  if (window.location.hash.substring(1) !== tabId) window.location.hash = tabId;
  return false;
}
window.setStudentTab = setStudentTab;
```

Por qué `Alpine.$data`: es API pública de v3; `_x_dataStack` queda solo como fallback para
jsdom sin `window.Alpine`. **Riesgo: nulo** (solo añade).

Commit: `fix(student): helper único de navegación entre pestañas (Alpine v3)`

### A2 · Reemplazar los call sites de `__x`

| #   | Sitio                          | Hoy                                                     | Después                                                                                                                       | Riesgo |
| --- | ------------------------------ | ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| 2a  | `registrations.js:270-275`     | **muerto** (botón "Explorar eventos")                   | `return window.setStudentTab("events")`                                                                                       | bajo   |
| 2b  | `event_activities.js:92-97`    | muerto y sin usos en plantilla                          | **eliminar la función**                                                                                                       | nulo   |
| 2c  | `event_activities.js:100-144`  | 45 líneas, 3 selectores, 3 fallbacks                    | `goBack() { return window.setStudentTab("events"); }`                                                                         | bajo   |
| 2d  | `overview.js:250-304`          | 55 líneas + evento `navigate-to-tab` que nadie escucha  | `return window.setStudentTab("registrations")`                                                                                | bajo   |
| 2e  | `events.js:210-303`            | 90 líneas; funciona por fallback `_x_dataStack`         | `setStudentTab("event_activities")` \*\*y conservar el `dispatchEvent("load-event-activities", …)` (líneas 243-250 / 282-290) | medio  |
| 2f  | `event_activities.js:436-456`  | refresco cruzado con `registrationsManagerElement.__x…` | `getAlpineData('[x-data*="studentRegistrationsManager"]')`                                                                    | bajo   |
| 2g  | `dashboard.js:256,271,289,476` | `__x` en las 4 ramas de `refreshTabContent`             | se resuelve en A3                                                                                                             | —      |

⚠️ **2e es el único que hoy funciona de verdad**: no tocar su `dispatchEvent`.

- [ ] **A2** Commit: `fix(student): reemplaza la API de Alpine 2 (__x) por el helper de navegación`

### A3 · `refreshTabContent` real, sin doble petición

Riesgo detectado: `setActiveTab` despacha `tab:activated` en `dashboard.js:233` **antes**
de llamar `refreshTabContent` en `:236`, y `tabLazyBoot` (`app.js:525-537`) ejecuta el
`boot` síncronamente. Reactivar el refresco a ciegas haría **dos peticiones en la primera
visita**.

- [ ] **A3.1** — Añadir `this._booted = true;` como primera línea del callback de
      `tabLazyBoot` (patrón que `registrations.js:81` ya usa) en: `events.js:35`,
      `event_activities.js:67`, `history.js:40`, `overview.js:53`, `profile.js:23`.
- [ ] **A3.2** — En `refreshTabContent`, refrescar solo si ya arrancó:

```js
const m = getAlpineData('[x-data*="studentEventsManager"]');
if (m && m._booted && typeof m.loadEvents === "function")
  await m.loadEvents(m.pagination?.current_page || 1);
```

Ídem para `event_activities` (`refreshCurrentEventActivities`), `history` (`loadHistory`) y
`registrations` (`refreshRegistrations`, `dashboard.js:476`).

Resultado: primera visita = 1 petición; visitas siguientes = refresco ✓.
**Rollback propio**: `git revert` de A3 sin tocar A1/A2.

Commit: `fix(student): refresca Eventos/Histórico/Actividades al volver a la pestaña`

### A4 · Tests — `app/static/js/student/__tests__/navigation.test.js` (nuevo)

- [ ] **A4.1** `setStudentTab llama a setActiveTab vía Alpine.$data` (mockear
      `window.Alpine = { $data: () => ({ setActiveTab }) }` + `<div x-data="…">` en
      `document.body`, **antes** del `require`, con `jest.resetModules()`).
- [ ] **A4.2** `setStudentTab cae a location.hash si no hay componente`.
- [ ] **A4.3** `goToEvents (registrations) navega a "events"` ← **fallaría antes del fix**.
- [ ] **A4.4** `goBack (event_activities) navega a "events"`.
- [ ] **A4.5** `refreshTabContent no recarga si no arrancó` / `sí recarga si _booted`.
- [ ] **A4.6** `getAlpineData devuelve null con selector inexistente`.

### A5 · Verificación manual

- [ ] **A5.1** Estudiante → _Mis Preregistros_ vacío → **"Explorar eventos"** cambia de pestaña.
- [ ] **A5.2** Pestaña Eventos → abrir evento → flecha atrás → vuelve a Eventos.
- [ ] **A5.3** Histórico → Resumen → Histórico ⇒ el listado se refresca (hoy queda viejo).
- [ ] **A5.4** `F12 → Network`: la primera entrada a Eventos hace **1 sola** petición a `/api/events`.

---

## 4. Fase C — Modal multidía (XSS + handler filtrado)

- [ ] **C1** — Escapar `activity.name` (`event_activities.js:845-847`) y las fechas
      (`:854-855`) con un `escapeHtml()` o construyendo el nodo con `createElement` +
      `textContent`.
      Prueba: actividad llamada `Test <img src=x onerror=window.__pwned=1>` ⇒
      `window.__pwned === undefined`.
      Commit: `fix(student): escapar el HTML del modal multidía (XSS)`
- [ ] **C2** — Mover `inflightRegistrations.add(activity.id)` a antes de
      `event_activities.js:332` (hoy está en la `:360`, después de abrir el modal ⇒ doble
      clic = dos modales con `id="multiday-confirm-modal"`). Envolver desde ahí en
      `try/finally` para que **todos** los caminos borren el id, incluido el `return` por
      401 de `:374-377` (hoy deja la actividad no registrable durante la sesión).
- [ ] **C3** — `document.onkeydown` (`:906`) → `addEventListener` + `removeEventListener`
      en `closeModal()` y en la confirmación. Añadir `role="dialog" aria-modal="true"`
      `aria-labelledby`, foco inicial en "Sí, preregistrarme" y devolución del foco.
- [ ] **C4** — Tests en `student/__tests__/multiday_modal.test.js`: - [ ] nombre con HTML no se inserta como marcado. - [ ] Escape cierra y el listener queda fuera (segunda tecla no hace nada). - [ ] doble clic ⇒ un solo modal en `document.body`.

---

## 5. Fase D — Doble envío y datos

- [ ] **D1** — Estado `submitting` en `registrations.js`: añadir `submitting: false`,
      envolver `confirmCancelRegistration` (`:189`) y `reRegisterForActivity` (`:229`) en
      `try/finally`; el `return` por 401 debe pasar por el `finally`.
      En `registrations.html:391` y `:537`: `:disabled="submitting"` + `opacity-50` +
      spinner `ti-loader-2`.
      Prueba: dos `click` ⇒ `fetch` llamado **una** vez (mock).
      Commit: `fix(student): bloquea el doble envío al cancelar y reactivar un preregistro`
- [ ] **D2** — `from`/`to` desde la API en `event_activities.js:259-266`
      (`from: data.from ?? 0`, `to: data.to ?? 0`; el backend ya los calcula en
      `activities_bp.py:220-221`). Revisar si `registrations.js#loadRegistrations` repite
      la fórmula con `20` y aplicar lo mismo.
- [ ] **D3** — Unificar el chequeo de cupo: `event_activities.js:701` pasa de `!== null` a
      `!= null` (igual que `:762`). Prueba: `{max_capacity: undefined}` ⇒
      `canRegisterForActivity === true` y `availabilityCode === "available"`.
- [ ] **D4** — Barra final del endpoint: unificar en `/api/registrations/` (con `/`) en
      `event_activities.js:287`, `overview.js:103,210`, `registrations.js:111,242`.
      Ahorra un `308` por petición. Prueba manual: carga de preregistros y de overview.

---

## 6. Fase B — Seguridad (backend ⇒ requiere aprobación de `pytest`)

> La Fase B es **independiente** de A/C/D: se puede intercalar en cualquier momento.

- [ ] **B1** — `@jwt_required()` en `students_bp.py:307` (ruta `:308`
      `…/hours-by-event`) y `:391` (ruta `:392` `…/event/<id>/details`).
      Seguro: los únicos llamadores son `student/history.js:77,111` y
      `admin/students.js:233,281`, ambos con `getAuthHeaders()`; `jwt_required` ya está
      importado (línea 2).
      Tests: 200 con token / 401 sin token.
      Commit: `fix(api): exige JWT en los endpoints de horas por evento del estudiante`

- [ ] **B2** — IDOR en `GET /api/registrations/` (`registrations_bp.py:150-160`).
      Copiar el patrón que el mismo archivo ya usa en el POST (líneas `23` y `38-47`):

```python
user, user_type, error = get_user_or_403()
if error:
    return error
if user_type == "student":
    own = user.id if user is not None else None
    if student_id is not None and own is not None and int(student_id) != own:
        return jsonify({"message": "Acceso denegado."}), 403
    student_id = own
```

Tests: estudiante A no puede leer `?student_id=B` (403) · admin sí · sin token ⇒ 401.
Commit: `fix(api): un estudiante solo puede listar sus propios preregistros`

### B3 · Endpoint dedicado de búsqueda (decisión D-1)

- [ ] **B3.1** — Nuevo `GET /api/students/lookup?control_number=` en `students_bp.py`.
  - Respuesta: `{ student: { control_number, full_name, career, email }, source: "local"|"external" }`
    o `404`. Mismo contrato que `/validate` para que el cambio de front sea mínimo.
  - Lógica: (1) `Student.query.filter_by(control_number=…).first()` → `source:"local"`;
    (2) si no existe → proxy al MAB (misma lógica que `validate_student_proxy`,
    `students_bp.py:244-307`, extraída a un helper `_lookup_external(control)` para no
    duplicar) → `source:"external"`.
  - Solo esos 4 campos (nada de `registrations`/`attendances`).
  - Sin `@jwt_required()` (los flujos son anónimos) **pero** con rate limit usando
    `SlidingWindowLimiter` (patrón de `auth_bp.py:219`, p. ej. 20 req/min por IP).
- [ ] **B3.2** — Migrar los 2 llamadores públicos a `/lookup` conservando `source`:
  - `public/registrations_public.js:699-718` (buscaba con `/api/students/?search=`).
  - `public/staff_walkin.html:215-240` (ídem).
  - [ ] Verificar que `walkinLookupState` / `walkinFoundSource` siguen igual.
- [ ] **B3.3** — Proteger `GET /api/students/` (`students_bp.py:24`) con `require_admin`
      (`app/utils/auth_helpers.py:56`) **una vez migrados los públicos**.
  - [ ] Confirmar que los 5 llamadores admin mandan token: `admin/students.js:113,789`,
        `admin/registrations.js:211`, `admin/reports.js:367`, `admin/attendances.js:829`.
  - [ ] Confirmar que ningún consumidor externo (MAB u otro) lo llama sin token.
- [ ] **B3.4** — Proteger `GET /api/students/<id>` (`students_bp.py:94`) con
      `require_admin` (sin llamadores del front localizados).
- [ ] **B3.5** — `/validate`: dejar de usarlo desde nuestro front (ya cubierto por
      `/lookup`) y decidir su destino → pregunta Q1.
- [ ] **B3.6** — Tests pytest de `/lookup` (local, externo, 404, rate limit) + de que
      `GET /api/students/` devuelve 401/403 sin admin.

Commit sugerido: `feat(api): endpoint dedicado de lookup de estudiante y listado restringido a admin`

- [ ] **B5 (opcional)** — Peso del listado: `students_bp.py:78` con `per_page=1000`
      (`admin/reports.js:367`) y schema con relaciones anidadas ⇒ payload grande + N+1.
      Evaluar `exclude=["registrations", "attendances"]` → pregunta Q2.

---

## 7. Fase E — Filtros del estudiante (decisión D-2: habilitar)

- [ ] **E1** — Backend `activities_bp.py`:
  - [ ] Soportar `sort=start_datetime:asc|desc` (hoy solo `name` ⇒ cae a
        `created_at desc`; verificado en `:142-160`). Opcional: `duration_hours`.
  - [ ] Quitar el filtro duplicado de `activity_type` (`:79` y `:131`).
  - [ ] Revisar el parámetro muerto `type` (`:77`, se pisa en `:78`; nadie lo usa,
        verificado con grep) → eliminarlo con cuidado o documentarlo.
  - Tests pytest: orden por fecha asc/desc, `activity_type`, `search`.
  - Commit: `feat(api): sort por start_datetime y sin filtro de tipo duplicado`
- [ ] **E2** — Frontend `event_activities.html` + `.js`:
  - [ ] Quitar el comentario: `event_activities.html:64` (`<!--<div …`) y `:116` (`…</div>-->`).
  - [ ] Opciones de tipo: quitar "Magistral" (el backend lo excluye con
        `for_student=true`, devolvería 0 siempre). Preferible: generar las `<option>` a
        partir de los tipos presentes en `activities` → pregunta Q3.
  - [ ] `per_page`: de `2000` a `100` (`event_activities.js:207`) para que la paginación
        exista de verdad.
  - [ ] Aplicar **D2** (`from`/`to` de la API) para que "Mostrando X a Y de Z" sea correcto.
  - [ ] Comprobar que `@input.debounce.300ms="loadActivities()"` (línea 71),
        `@change="loadActivities()"` (81, 97) y el botón Buscar (`:108-111`) siguen activos.
  - Tests Jest: filtro por tipo, búsqueda, orden, `pagination.from/to` desde la API.
  - Commit: `feat(student): filtros y paginación de actividades del evento operativos`

---

## 8. Fase F — Mantenibilidad (al final)

- [ ] **F5** — Mover los `<script>` a `{% block scripts %}` en `student/base.html`
      (después de `app.js`, `base.html:149`). Hoy están dentro del bloque `content`
      (antes de los helpers): `event_activities.js` en `dashboard.html:44`, los otros 5 en
      sus parciales, más `impersonation.js` y `dashboard.js` en `student/base.html:332-333`.
      **Hacerlo primero dentro de la fase**: cambia el orden de ejecución y conviene aislarlo.
- [ ] **F1** — `redirectToLogin()` → helper global en `app.js` (junto a `getAuthHeaders`,
      línea 143) y los 7 métodos delegan con el patrón que ya usa `logout()`
      (`dashboard.js:452-469`). Unificar `history.js`: hoy omite
      `removeItem("studentProfile")`.
- [ ] **F2** — `getCurrentStudentId()` → helper global; unificar a la semántica más
      robusta (la de `history.js:201`: `studentProfile` → JWT `sub|user_id|id`).
- [ ] **F3** — Formateadores → delegar en `window.dateHelpers` con el patrón de
      `events.js:306-314`; eliminar las copias en los 6 archivos.
- [ ] **F4** — `viewEventDetails` duplicado → dejar uno (`dashboard.js:382` / `events.js:154`).
- [ ] **F6** — A11y: `@keydown.escape.window` en `events.html:202`,
      `registrations.html:335` y `:402`, `history.html:247`; `role="dialog"`
      `aria-modal="true"` en los 5 modales; `aria-label` en botones de solo icono
      (`event_activities.html:11` flecha atrás, botones de cerrar).

---

## 9. Fase G — Cobertura (va embebida en cada fase, no al final)

| Archivo                                       | Cubre                                                                  | Relacionado |
| --------------------------------------------- | ---------------------------------------------------------------------- | ----------- |
| `student/__tests__/navigation.test.js`        | navegación + refresco                                                  | A4          |
| `student/__tests__/multiday_modal.test.js`    | XSS, Escape, doble apertura                                            | C4          |
| `student/__tests__/registration_flow.test.js` | `canCancelRegistration`, `canReRegisterForActivity`, doble envío, cupo | D1, D3      |
| ampliar `session_dates.test.js`               | `from/to` desde la API                                                 | D2, E2      |
| `tests/api/test_students_auth.py`             | 401/403 en rutas de students + IDOR de registros                       | B1, B2, B3  |
| `tests/api/test_activities_sort.py`           | orden y filtros                                                        | E1          |

---

## 10. Orden de ejecución

```text
FASE A   A1 → A2 → A4 → A5(verificación manual) → A3 → A4(completar) → commit
FASE C   C1 → C2 → C3 → C4 → commit
FASE D   D1 → D2 → D3 → D4 → commit
FASE B   B1 → pytest → B2 → pytest → B3.1 → B3.2 → B3.3 → B3.4 → pytest   (requiere aprobación)
FASE E   E1 → pytest → E2 → Jest → commit
FASE F   F5 → F1 → F2 → F3 → F4 → F6 → commit
```

Matriz de riesgo:

- **Bajo** (añaden o sustituyen 1:1): A1, A2, C1, C2, D3, D4, F1, F3.
- **Medio** (rollback propio): **A3**, 2e, B3.3, F5.
- **Bajo pero backend** (pytest): B1, B2, B3, E1.
- **Bajo-medio**: C3, D1, F2, F6.

---

## 11. Preguntas abiertas

- **Q1 (B3.5)** — ¿Qué hacemos con `GET /api/students/validate` una vez exista `/lookup`?
  Opciones: (a) dejarlo público con rate limit, (b) `require_admin`, (c) redirigirlo
  internamente a `/lookup`. _Recomendado: (a) + rate limit_, porque está documentado como
  "proxy público" y podría ser intencional para sistemas externos.
- **Q2 (B5)** — ¿El admin necesita `registrations`/`attendances` anidados en
  `GET /api/students/`? Si no, se excluyen y se gana mucho peso.
- **Q3 (E2)** — Las `<option>` de tipo: ¿lista fija sin "Magistral" o derivada de las
  actividades del evento? _Recomendado: derivada._
- **Q4** — ¿Se commitea este documento (`docs/STUDENT_MODULE_REVIEW.md`) con el primer
  commit de la Fase A, o al cierre?

---

## 12. Registro de avance

| Ítem | Estado       | Commit | Fecha |
| ---- | ------------ | ------ | ----- |
| A1   | ⬜ pendiente |        |       |
| A2   | ⬜ pendiente |        |       |
| A3.1 | ⬜ pendiente |        |       |
| A3.2 | ⬜ pendiente |        |       |
| A4   | ⬜ pendiente |        |       |
| A5   | ⬜ pendiente |        |       |
| C1   | ⬜ pendiente |        |       |
| C2   | ⬜ pendiente |        |       |
| C3   | ⬜ pendiente |        |       |
| C4   | ⬜ pendiente |        |       |
| D1   | ⬜ pendiente |        |       |
| D2   | ⬜ pendiente |        |       |
| D3   | ⬜ pendiente |        |       |
| D4   | ⬜ pendiente |        |       |
| B1   | ⬜ pendiente |        |       |
| B2   | ⬜ pendiente |        |       |
| B3.1 | ⬜ pendiente |        |       |
| B3.2 | ⬜ pendiente |        |       |
| B3.3 | ⬜ pendiente |        |       |
| B3.4 | ⬜ pendiente |        |       |
| B3.5 | ⬜ pendiente |        |       |
| B3.6 | ⬜ pendiente |        |       |
| E1   | ⬜ pendiente |        |       |
| E2   | ⬜ pendiente |        |       |
| F1   | ⬜ pendiente |        |       |
| F2   | ⬜ pendiente |        |       |
| F3   | ⬜ pendiente |        |       |
| F4   | ⬜ pendiente |        |       |
| F5   | ⬜ pendiente |        |       |
| F6   | ⬜ pendiente |        |       |

### Historial de decisiones

| Fecha      | Decisión                                                                             |
| ---------- | ------------------------------------------------------------------------------------ |
| 2026-10-05 | Plan creado; alcance completo A–G; decisiones D-1, D-2 y D-3 tomadas por el usuario. |
