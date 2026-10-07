# MIGRATION - Evaluación técnica para migración / refactorización

1. Volumen y complejidad de las vistas actuales

- No. aproximado de templates/pantallas: 28 (carpeta app/templates incluye admin, student, public y auth).

- Pantalla más compleja (interacciones JS): el panel administrativo de Asistencias (app/static/js/admin/attendances.js, ~1510 LOC). Incluye check-ins rápidos, modales, mutaciones in-place, sincronizaciones y operaciones por lotes (batch), por lo que requiere pruebas y coordinación con el backend.

- Componentes reutilizables: sí. app/static/js/app.js expone helpers globales (safeFetch, getAuthHeaders, showToast, dateHelpers). Módulos Alpine (app/static/js/admin/\*.js) siguen patrón factory reutilizable; plantillas parciales en app/templates/admin/partials se usan en múltiples pantallas.

2. Integraciones externas críticas

- Servicio externo de autenticación de alumnos: sí. `POST /api/auth/student-login` y `POST /api/registrations/self` validan en proceso contra <http://apps.tecvalles.mx:8091/api/validate/student> (`requests.post` compartido en `app/services/student_auth_service.py`). Desde la ronda 2026-10-06 ya **no** hay llamada HTTP interna de `/api/registrations/self` a `/api/auth/student-login` (se eliminó el loopback al `request.host_url`).

- Otras integraciones: no se encontraron integraciones de pagos, webhooks o servicios de streaming. No hay referencias a Stripe/PayPal/Pusher/Socket.io.

- Consideraciones: la integración con el servicio de autenticación externo ya maneja timeouts y errores (401/503). Si se requieren muchas integraciones asíncronas, planificar cola/worker (Celery/RQ) o circuit-breaker/retry (tenacity) y observabilidad.

3. Reportes y generación de archivos

- La app usa pandas + openpyxl (y openpyxl directo) para producir XLSX/CSV.

- ¿Descargables o embebidos?: descargables. Muchos endpoints (students, activities, reports, public_registrations) usan send_file / Response con header Content-Disposition: attachment; el frontend extrae ese header y fuerza descarga (app/static/js/admin/reports.js y public clients). No se visualizan embebidos por defecto.

4. Estado actual del frontend (legacy)

- Líneas de JS: ~15.1k LOC en app/static/js (11,829 LOC de producción + 3,305 LOC de tests = 15,134; conteo automático verificado).

- Deuda técnica notable:
  - Uso de variables globales (window.\*) para helpers y estado compartido.
  - Interceptor global de fetch que captura la referencia a fetch en carga — esto complica tests y rehacer el loader sin romper compatibilidad (tests deben mockear fetch antes de require()).
  - Módulos que capturan referencias en carga (causa de jest.resetModules() en tests).
  - Lógica duplicada y funciones utilitarias no centralizadas (aunque dateHelpers existe).

- Tests frontend existentes: sí (múltiples archivos en app/static/js/**tests** y admin/**tests**). Si se refactoriza la carga o la API pública de app.js, habrá que actualizar tests para mockear fetch/localStorage antes de require() y posiblemente reescribir pruebas que dependen de efectos de carga.

5. Requisitos de tiempo real

- Estado actual: no hay WebSockets ni integración realtime. No hay uso de Socket.io, Pusher, SSE, etc.

- ¿Necesidad? Depende del producto: actualmente la app hace operaciones batch y sincronizaciones (attendances sync). Si se desea visualización en vivo (contador de asistencias en tiempo real, notificaciones push), requeriría añadir infraestructura realtime (WebSocket endpoint o SSE + una capa de pub/sub). Para cargas altas, usar Redis pub/sub o un servicio gestionado.

Autenticación (JWT + localStorage + validación externa)

- Flujo actual de login:
  - Administradores: POST /api/auth/login. El servidor valida credenciales locales (User model) y genera un JWT con create_access_token (Flask-JWT-Extended). La respuesta contiene { access_token, user }.
  - Estudiantes: POST /api/auth/student-login. El servidor reenvía credenciales al servicio externo (<http://apps.tecvalles.mx:8091/api/validate/student>). Si la validación externa es exitosa, crea/actualiza el Student local y emite un access_token similar.
  - Registro in situ (`/api/registrations/self`) valida las credenciales **en proceso** con la misma función que `student-login` (`student_auth_service.validate_student_credentials`), compartiendo el mismo rate-limit por número de control y por IP: no hace llamadas HTTP internas (ronda 2026-10-06).

- Logout (revocado server-side — implementado):
  - POST /api/auth/logout registra el `jti` del token vigente en la tabla `revoked_tokens` (modelo `RevokedToken` en app/models/revoked_token.py + migración alembic `20260927_add_revoked_tokens`, head de `20251031_create_app_settings`) y purga oportunamente las filas de tokens ya vencidos.
  - Flask-JWT-Extended consulta el blocklist en cada request vía `@jwt.token_in_blocklist_loader` (`app/__init__.py`): un token revocado responde 401 hasta su `exp`; los demás tokens del mismo usuario siguen válidos. Si la migración no se ha aplicado, el loader emite un warning y no bloquea (la app no cae).
  - Frontend: el logout quedó centralizado en `logout()` de app/static/js/app.js — tras el confirm, dispara `POST /api/auth/logout` con `keepalive: true` vía `safeFetch` ANTES de limpiar localStorage y redirigir (la petición sobrevive al cambio de página). Los factories de admin/student (dashboard, overview, profile) delegan en `window.logout` y conservan fallback local para tests que no cargan app.js.

- Refresh de tokens:
  - No existe un endpoint de refresh ni mecanismo de refresh token en el backend (no se usan create_refresh_token ni refresh endpoints).
  - El cliente gestiona expiración: app/static/js/app.js decodifica el payload del JWT (exp) y muestra warnings/expiración; el interceptor maneja 401 mostrando toast y forzando redirect al login. En práctica: se requiere re-login cuando el token expira.

- Riesgos y recomendaciones de mejora:
  1. Almacenamiento en localStorage es vulnerable a XSS; considerar cambiar a HttpOnly Secure cookies para tokens o usar rotating refresh tokens guardados con mayor protección.
  2. Implementar refresh tokens (refresh token HttpOnly + short-lived access token) para mejorar UX (sesiones silenciosas) y permitir revocación. Usar librería de control de tokens con revocation-list o DB de sesiones si se necesita logout server-side.
  3. Considerar refresco silencioso (silent refresh with iframe or background refresh) o revocar refresh tokens tras uso (rotating refresh tokens) para seguridad.
  4. ✅ Implementado: logout server-side con revocación por `jti` (ver sección Logout). Solo quedaría, si el producto lo pide, rotación de refresh tokens.
  5. Monitorizar y establecer tiempos de expiración adecuados. En APIs públicas usar HTTPS obligatorio y SameSite cookie attributes si se migran a cookies.

Baseline de limpieza previo a la migración (todo verificado con pruebas)

- Puntos muertos corregidos:
  - "Editar evento" del overview del dashboard (admin/partials/overview.html): ahora hace `setActiveTab('events')` y emite `event:edit-request` (escuchado en `init()` de events.js que abre el editor). Motivo: el overview vive en el scope de `adminDashboard()` y events en `eventsManager()`; Alpine no permite invocar métodos entre scopes, y no existe puente para dos instancias de la misma factory.
  - Botón "Sincronizar estudiantes" de la pestaña Students (students.js `syncStudentsFromAPI()` apuntaba a una ruta inexistente): se implementó `POST /api/students/sync-external` (upsert masivo desde el sistema externo con paginación estilo Laravel, defensivo ante envolventes y campos variables; responde `{created, updated, skipped, total_received}`; 503 si el externo falla).
  - `GET /api/reports/attendance_list` devolvía 500: creada la plantilla app/templates/admin/reports/attendance_list.html (lista imprimible con columnas por día cuando la actividad es multi-día). Nota: la ruta exige header `Authorization`, por lo que no sirve navegar a ella directamente; se abre desde el panel de Reportes → "4. Lista de asistencia (imprimible)" (`printAttendanceList()` en `reports.js`: pestaña abierta de forma síncrona → fetch autenticado → blob), con tests Jest en `reports.test.js`.

- Endpoints depurados: 14 rutas eliminadas (0 referencias en frontend; verificado también contra tests/docs/scripts). Los tests que únicamente probaban endpoints borrados se eliminaron o recortaron junto con ellos.
  - Grupo A (cero referencias en todo el repo): GET /api/students/external-search, POST /api/students/import-external/<control>, GET /api/activities/<id>/attendances, GET /api/activities/<id>/registrations, GET /api/activities/<id>/export_registrations.xlsx, GET /api/events/<id>/activities, GET /api/students/<id>/activities, GET /api/public/registrations/lookup-student.
  - Grupo B (referenciados solo por tests; borrados con sus tests por decisión explícita del usuario): GET /api/students/search, POST /api/attendances/check-in, POST /api/attendances/check-out, POST /api/attendances/bulk-create, POST /api/attendances/<id>/recalculate, GET /api/reports/preregistrations_by_career.
  - Nota: `scripts/references/*.txt` contienen snapshots antiguos del código (no son código en ejecución); los endpoints "sustituidos" por equivalents nuevos (register, batch, batch-checkout, /api/students?search=) no se referencian desde el código actual.
  - Conteo de rutas (url_map): 95 en HEAD → 82 (14 borradas + 1 añadida: sync-external).

- Corrección de la suite de pruebas: `config.py` `TestingConfig` define ahora `SQLALCHEMY_ENGINE_OPTIONS` propios de SQLite. El commit `c1ee6c6` añadió `connect_args.connect_timeout` (argumento de pymysql) a la config base, y SQLite rechazaba esa kwarg → los 208 tests fallaban en fixture con `TypeError` (esto ocultaba el estado real de la suite).

- Estado de pruebas (2026-09-28, tras las correcciones de asistencia/enlaces):
  - pytest: **166 passed / 11 failed / 21 errors** (baseline 2026-09-27: 148/21/21 → +18 passed, −10 failed, errores sin cambios → cero regresiones). Los 11 fallos restantes son preexistentes, atribuidos uno a uno: **(1)** 10 tests de settings bloqueados porque `.env` local define `APP_TIMEZONE` (`test_settings_e2e` ×6 — uno además por la API vieja `is_locked_by_env`, inexistente en el código actual — y `test_settings_manager` ×4); CI no lleva `.env` → ahí pasan. **(2)** `test_activity_service_slug::test_create_generates_slug` llama a `create_activity()` sin contexto de app (revienta en `db.session.get`) → nunca pudo pasar en su forma actual; la generación automática de slug del servicio queda cubierta por `tests/api/test_activities.py::test_create_activity_generates_public_slug`. Los **21 errors** = 13 de `app/tests/api/test_reports_hours_compliance.py` (copia anidada trackeada; pendiente moverla a `tests/` o eliminarla — no llega a ejecutarse) + 8 por drift de fixtures: `tests/test_public_slug_views.py` y `tests/test_public_endpoints_slug.py` piden un fixture `db_session`/`event_factory` que no existe en `tests/conftest.py`.
  - Jest: **146 passed / 18 failed** en 4 suites (reports, activities consolidated, student/history, activity_editor.slug): mismos 18 preexistentes verificados con stash en HEAD puro → cero regresiones; los tests nuevos de esta ronda (modal de enlaces) pasan.

- Limpieza quirúrgica de tests (2026-09-29, opción 1: solo `tests/` y tests JS; API, modelos y BD intactos):
  - pytest: **198 passed / 0 failed / 0 errors** (baseline 2026-09-28: 166/11/21 → −11 failed, −21 errors, +32 passed, cero regresiones; el único `xpassed` es `test_pause_view_shows_expired_after_activity`, con `xfail` preexistente por timing). Fixes: **(1)** aislamiento del `.env` local en `test_settings_e2e` y `test_settings_manager`: fixture autouse que borra `APP_TIMEZONE`/`APP_APP_TIMEZONE` con `monkeypatch` y limpia `SettingsManager._cache` (caché de clase que persiste entre tests, TTL 10 s); `test_env_lockea_cambio_desde_ui` reescrito contra la API vigente (`SettingsManager.get` prioriza ENV y `set_in_db` lanza `ValueError: locked by environment variable` — la API admin calcula el lock inline, `is_locked_by_env` ya no existe). **(2)** `test_create_generates_slug`: `sample_data` (evento real en rango 2024-01-01), datetimes parseados en vez de strings y `modality` (columna NOT NULL). **(3)** `tests/conftest.py` gana los fixtures `db_session`, `event_factory` y `activity_factory` (drift: nunca existieron en git; los consumen `test_public_slug_views.py` y `test_public_endpoints_slug.py`). **(4)** `app/tests/api/test_reports_hours_compliance.py` movido con `git mv` a `tests/api/` (era la única cobertura de `/api/reports/hours_compliance*` y `/api/reports/student_participations*`; pasó sin cambios de aserciones) y directorios `app/tests/` eliminados. **(5)** `test_self_register_by_slug_renders_form` asienta sobre `data-activity-id="<slug>"` (la plantilla no contiene `self_register.html` ni `activity_token`).
  - Jest: **161 passed / 0 failed / 15 suites** (baseline: 146/18). De los 18 fallos: 15 en `reports.test.js` — 12 reescritos contra la implementación real (`matrix_headers/rows/footer`, `filters.event_id` compartido con el reporte de horas, await al timer de 50 ms de `onEventChange`, toast con el mensaje del servidor) y 3 borrados por aspiracionales (`onHoursEventChange` y `apply10PlusFilter` ×2: no existen en `reports.js` ni se usan en `reports.html`) — y 3 sueltos: `history.test.js` (el mock de `localStorage` no reemplazaba al nativo de jsdom → token real con `localStorage.setItem`), `activities.consolidated.test.js` (faltaba `currentActivity.id = 1`) y `activity_editor.slug.test.js` (default `currentActivity` sin `public_slug`, añadido en `activity_editor.js` incluyendo `resetCurrent`).
  - Hallazgo: `activity_editor.js` no está referenciado por ninguna plantilla (el editor real es `activities.js`, que ya maneja `public_slug`); es código posiblemente muerto — candidato a eliminación en una tarea dedicada, fuera de esta limpieza.

- Correcciones de asistencia y enlaces públicos (2026-09-28):
  - `POST /api/attendances/batch-checkout` ahora **despausa automáticamente** las filas con pausa abierta (instructor olvidó reanudar o la ventana pública expiró): la pausa vigente se cierra con duración cero y no descuenta el tiempo restante. Cambio de contrato (aditivo, backward-compatible): `summary` incluye `resumed_paused` (conteo de filas despausadas). Bug de origen: en magistrales las asistencias quedaban `Parcial`/`Ausente` porque el cálculo usaba `resume_time or now` y descontaba toda la sesión posterior a la pausa olvidada.
  - `POST /api/attendances/register` con `check_out_time` ahora **recalcula** `attendance_percentage` y `status` vía `calculate_attendance_percentage` (antes solo persistía el timestamp): una asistencia creada como `Parcial` (p. ej. self check-in de magistral) se quedaba en `Parcial`/0% para siempre al hacer checkout por esta vía. `mark_present` sigue siendo override manual (100%, no se recalcula). El checkout también cierra pausas abiertas. Efecto colateral positivo: las actividades relacionadas (umbral ≥80%) ahora ven el porcentaje fresco.
  - Ventana pública de reanudación (`public_pause_available_until_after_end_minutes`): default 5 → **60 minutos** (`app/services/settings_manager.py` + `scripts/initialize_app_settings.py`). ⚠️ El seed omite filas existentes: en despliegues donde la fila ya existe con valor 5, actualizarla desde Admin → Settings (o eliminar la fila y re-ejecutar el seed).
  - Enlaces para jefes: `fetchActivityToken()` en `activities.js` ya no aborta si la actividad no tiene `public_slug`; genera los 4 enlaces usando el **ID numérico** como fallback (el backend acepta slug o ID en todas las vistas públicas) y muestra el aviso "Sin slug público". Verificación de generación automática de slugs: `POST /api/events/` y `POST /api/activities/` generan `public_slug` + `public_url` (tests nuevos en `tests/api/test_events.py` y `tests/api/test_activities.py`). Nota: los links del año pasado (formato `/public/registrations/<token>`) murieron con el refactor `c10cbab` → regenerar y compartir los links con slug en el nuevo evento.
  - Tests nuevos: `test_batch_checkout.py` (+2: despausa real y dry_run), `test_attendances_register.py` (+2: recálculo y despausa en checkout), `test_settings_manager.py` (+1: default 60), `test_events.py` y `test_activities.py` (+1 cada uno: slug+public_url), `activities.consolidated.test.js` (+2: enlaces por slug y fallback a ID). Reparado `tests/api/test_public_pause_attendance_timezone.py`: sus 5 tests fallaban preexistentemente por la deprecación de `generate_public_token`; migrados a resolución por ID numérico/`activity_id`.

  - Hallazgo clave para los enlaces (punto 5): `@pre_dump` de `ActivitySchema` copiaba una lista blanca de atributos **sin `public_slug`**, por lo que _ningún_ endpoint de actividad devolvía el slug (el `public_url` que agregaba `activities_bp` era código muerto y el modal de enlaces nunca recibía slug). Añadido `public_slug` a la lista blanca → listado, detalle y creación de actividades ahora incluyen `public_slug` (y por tanto `public_url`). Con esto + la auto-generación de slug en create (evento y actividad) + fallback a ID numérico en el modal, el flujo "crear nuevo evento → compartir enlaces con jefes" queda completo.
  - `datetime.utcnow()` (Python 3.14 + `filterwarnings = error::DeprecationWarning:app.*` en pytest.ini) en `settings_manager.py` (2 sitios) y `reports_bp.py` (1) hacía fallar las lecturas de settings en tests: reemplazado por `datetime.now(timezone.utc).replace(tzinfo=None)` (naive-UTC idéntico, patrón ya usado en `revoked_token.py`). Sin este fix, el nuevo default de 60 min se hacía visible como fallo en `test_app_settings_convenience_methods`.
  - Tests reparados (preexistentes, datos/fixtures rotos): `tests/test_activities.py` y `tests/api/test_activities.py` (fechas con offset `-06:00` para superar la validación de rango evento↔actividad con la interpretación naive→APP_TIMEZONE), `tests/test_slug_utils.py` (DummyModel con columna simulada que expone `.like()`), `tests/api/test_public_pause_attendance_timezone.py` (5 tests: `generate_public_token` deprecado → resolución por ID numérico/`activity_id`).
- Despliegue (producción, 2026-09-29): ✅ `flask db upgrade` ejecutado (`alembic_version` reparado a un solo registro en `20260927_add_revoked_tokens`, head). ✅ Seed de settings en BD (4 filas editables: `app_timezone=America/Mexico_City`, `public_pause_available_from_seconds=0`, `public_pause_available_until_after_end_minutes=60`, `public_confirm_window_days=30`). ✅ **Código desplegado con `./deploy.sh` y smoke-test manual pasado (verificado 2026-10-02)**: logout con token viejo → 401, enlaces públicos, y Admin → Settings muestra las 4 filas (pausa = 60).

## Créditos complementarios multi-evento (ronda 2026-10-01)

Commits: `2ece1dd` (servicio unificado de horas), `2b2710e` (event_ids), `07d02e2` (exclusión derivada), + el de esta sección (credit_overrides). Tag `v0.9` = última versión en producción (rollback rápido).

- **Fuente única de horas**: `app/services/hours_service.py` — Registration (`Confirmado`/`Asistió`) + Attendance (`Asistió`, walk-ins), dedup por actividad, `round(total, 2)` antes de comparar umbrales (`CREDIT_MIN_HOURS = 10.0`). Los 6 call sites previos (complementary-credits ×2, hours_compliance ×2, hours-by-event, has_credit del detalle) ahora lo usan; se eliminó ~150 líneas duplicadas.
- **Lista de créditos con walk-ins**: la lista del 45° Aniversario pasa de **238 → 518** estudiantes (antes solo consultaba Registrations `Asistió`; `hours_compliance` ya contaba los 3023 pares walk-in). Control post-deploy: `GET /api/students/complementary-credits?event_id=1` debe dar ≈518, consistente con `/api/reports/hours_compliance?event_id=1`.
- **Multi-evento**: `GET /api/students/complementary-credits?event_ids=1,3` (acepta comas y/o repetido; `event_id` simple intacto byte a byte). Respuesta aditiva: `events[]` (orden cronológico), `event: null` en modo multi, `hours_by_event`/`activities_by_event` por estudiante, `excluded_already_credited`, `excluded_by_override`.
- **Exclusión derivada (earliest-crossing)**: con N eventos seleccionados, solo entra quien cruza las 10 h en el **último** evento cronológico; quien cruzó antes ya está acreditado y se omite. Con un solo evento la regla no cambia nada (cruce en el único evento).
- **Overrides manuales**: tabla `credit_overrides` (una fila por estudiante: `decision` include/exclude, `reason`, timestamps). API: `GET/POST /api/students/credit-overrides` (upsert) y `DELETE /api/students/credit-overrides/<student_id>` (admin JWT). `include` fuerza la inclusión aunque falle la regla derivada o no alcance 10 h (incluso sin participaciones → fila sintética con 0 h); `exclude` omite siempre.
- Estado de pruebas: **pytest 239 passed / 0 failed / 0 errors** (+1 xpass preexistente); **Jest 173 passed / 15 suites** (UI multi-evento + overrides: selector de eventos con checkboxes, columnas de desglose por evento, badges de omitidos, acciones de override por fila, sección de overrides aplicados y forzar inclusión por búsqueda de control).

### ⚠️ Paso de despliegue OBLIGATORIO (migración aditiva)

`entrypoint.sh` NO aplica migraciones automáticamente (`AUTO_MIGRATE=false` por defecto). Después de `./deploy.sh`, ejecutar **en el servidor**:

```bash
docker compose exec web flask db upgrade
```

- Nueva revisión: `20261001_add_credit_overrides` (down: `20260927_add_revoked_tokens`). **Solo `CREATE TABLE credit_overrides`** — no altera ni toca tablas existentes (sin riesgo de regresión de datos).
- Revisión encadenada: `20261002_add_credit_grants` (down: `20261001_add_credit_overrides`). Igual de aditiva: **solo `CREATE TABLE credit_grants`** + 3 índices. Mientras no exista, `load_grants_map()` devuelve `{}` y `credit_grants_available()` devuelve `False`: la lista se calcula sin exclusión por otorgamiento y el botón _Otorgar crédito_ aparece bloqueado en la UI (la descarga del Excel sigue funcionando). **No usar _Otorgar crédito_ antes de migrar**: el Excel se descargaría pero el registro fallaría y el archivo quedaría sin constancia.
- Mientras no se ejecute, la lista de créditos sigue funcionando: `load_overrides_map()` es defensivo (loguea warning y calcula sin overrides). Los endpoints CRUD de overrides devolverán 500 hasta que la tabla exista — migrar antes de usar esa UI.
- **Estado (verificado 2026-10-02): ⏳ AÚN PENDIENTE en producción** — `alembic_version` = `20260927_add_revoked_tokens` y la tabla `credit_overrides` no existe. Los botones _Omitir / Forzar inclusión_ de la UI de créditos responderán 500 hasta correr el `flask db upgrade` en el servidor. `credit_grants` también queda pendiente (va encadenada).

### Pendiente documentado (fuera de alcance de esta ronda)

- **Fase 3: tabla `credit_grants`** para evitar doble acreditación al re-exportar la lista a la plataforma externa (historial de grants por lote/evento) → **implementada en la ronda 2026-10-02**, ver la sección _Fase 3: credit_grants_ al final de este documento.
- Los overrides solo afectan la lista de créditos (vista admin); el badge del portal del estudiante (`has_complementary_credit` del detalle de evento) sigue puramente derivado.

## Fix de zona horaria en importación batch (ronda 2026-10-02)

Commit: `2602845` · Desplegado y verificado en producción el 2026-10-02.

- **Síntoma**: al subir `Plantilla Captura Actividades Eventos 2026.xlsx` (46° aniversario), las actividades se crearon con horarios **+6 h** (ej. 13:00 → 19:00), mientras la creación manual las guardaba bien.
- **Raíz**: `create_activities_from_xlsx` usaba `safe_iso()` —helper de LECTURA: interpreta el naive como hora local y lo convierte a UTC— para construir el payload de **escritura**. `create_activity` conserva el wall time que recibe y PyMySQL lo escribe sin convertir → MySQL quedaba con hora UTC; la lectura (`to_dict` → `safe_iso`) interpreta el naive como local y la UI mostraba el desfase.
- **Fix**: nuevo `iso_for_write()` en `app/utils/datetime_utils.py` (preserva el wall time; misma convención que `parse_datetime_with_timezone` del endpoint manual), usado por el importador en `activity_service.py`. `safe_iso` quedó marcado como solo-lectura en su docstring. Sin cambios de frontend (el preview raw del dry-run ahora muestra la hora local correcta).
- **Datos corregidos en producción (2026-10-02)**: 32 filas batch −6 h + Rally Día del Programador (id 107: start 00:00 → 12:00, error propio al editar) = **33 filas**. Guardas previas (cada fila verificada como exactamente Excel+6 h), candado optimista por fila (`WHERE id AND valor_previo`) y commit único. intactas: 8 filas corregidas manualmente, 4 manuales (67-70) y todo el 45°. Rollback: `rollback_horarios_46aniv_pre_tzfix.sql` (raíz del proyecto, **fuera del repo** por contener datos de prod).
- **Verificación post-deploy (2026-10-02)**: 41/41 filas == Excel (start y end), 45 filas en event 3 sin duplicados, round-trip UI muestra la hora del Excel en todas.
- **Tests**: **pytest 240 passed / 0 failed** (+`tests/services/test_activities_import_timezone.py`: celda datetime y celda texto ISO se guardan como hora local naive). Ruff limpio.
- **Idempotencia de re-importación**: con el fix desplegado, volver a subir el mismo Excel debe reportar `created=0` y 41 errores "Duplicada: actividad ya existe (omitir)". No re-importar con el código anterior desplegado (crearía duplicados +6 h).

## Fase 3: credit_grants — historial de otorgamientos (ronda 2026-10-02)

Objetivo: evitar que al re-exportar la lista a la plataforma externa se acredite dos veces al mismo estudiante y, a la vez, permitir que un estudiante libere **otro** crédito cuando junta 10 h frescas en otros eventos.

### Modelo

- Tabla `credit_grants` (migración `20261002_add_credit_grants`, 100% aditiva, down `20261001_add_credit_overrides`): una fila por `student_id + event_id` **gastado** (unicidad como red de seguridad), con `batch_id` (lote de la confirmación), `granted_by`, `granted_at` y `note`.
- **El evento es la unidad que se gasta**: al acreditar se registran los eventos que aportan horas NO gastadas desde el inicio hasta el cruce de 10 h; los posteriores al cruce quedan intactos para un crédito futuro.
- `compute_credit_rows()` (fuente única en `app/services/hours_service.py`) evalúa umbral y cruce sobre las horas **no gastadas** y añade a cada fila `hours_consumed`, `hours_available`, `crossing_event_id`, `grant_event_ids`, `granted_event_ids` y `already_granted`. Con `grants={}` (migración pendiente) el comportamiento es idéntico al anterior: cero regresiones.

### Flujo del admin (confirmación explícita)

1. Modal _Exportar Créditos_ → _Buscar Estudiantes_ → lista de **pendientes** (los ya otorgados quedan fuera y se cuentan en `excluded_already_granted`).
2. **Otorgar crédito (N)** → confirmación en pantalla → (a) descarga el XLSX de los pendientes y (b) `POST /api/students/credit-grants` con los mismos filtros y `confirm: true`. El orden es deliberado: si el POST falla, no se gastó nada y se reintenta sin doble acreditación.
3. **Descargar sin otorgar** solo genera el archivo (revisar / re-auditar).

### Decisiones de diseño

- El **Excel nunca incluye** a los ya otorgados: es el archivo que se sube al externo. El toggle _Ver ya otorgados_ solo afecta a la vista previa en pantalla y marca la fila con `already_granted`.
- El endpoint de lista acepta `include_granted=1` para auditar; el de export y el de otorgamiento **nunca** lo activan.
- `credit_grants_available` en la respuesta de la lista habilita/deshabilita el botón de otorgamiento según exista la tabla (evita descargar un archivo que no se puede registrar).
- Corrección incluida: la descarga del Excel usaba `window.open()` contra una ruta con `@jwt_required` (sin header `Authorization`) y abría una pestaña con 401; ahora baja con `fetch` autenticado + blob, igual que el resto de exportes.

### Despliegue

- `flask db upgrade` aplica `20261001` y `20261002` en cadena. Ver el estado en _Paso de despliegue OBLIGATORIO_.
- Tests: `tests/api/test_credit_grants.py` — auth, validaciones del POST, acreditación + exclusión de la lista, segundo crédito con horas frescas, no repetibilidad, fila forzada por override, Excel sin acreditados e historial por lote.

## Registro in situ y cierre de asistencia (ronda 2026-10-06)

### 1. Ventana de self check-in configurable

- Ventana única `[inicio - public_self_register_open_minutes_before_start, inicio + public_self_register_close_minutes_after_start]` (defaults **30 / 20 min**) calculada en `app/services/self_register_service.py` y usada por la vista GET, el POST y el countdown del frontend. Antes solo existía el límite superior, hardcodeado en 3 lugares, y **no había límite inferior**: un QR generado días antes dejaba el check-in abierto _antes_ de que empezara la actividad.
- Estados `open` / `not_open` / `closed` con mensajes distintos, expuestos al JS vía `data-activity-message` (el servidor manda: `data-activity-deadline` ya no lo calcula el cliente).
- **Despliegue**: `python scripts/initialize_app_settings.py` siembra las 2 keys nuevas para poder editarlas en Admin → Settings (también se pueden fijar por ENV: `APP_PUBLIC_SELF_REGISTER_OPEN_MINUTES_BEFORE_START` / `..._CLOSE_MINUTES_AFTER_START`).

### 2. Rate-limit y validación de credenciales en proceso

- `app/services/student_auth_service.py` (nuevo): fuente única de `validate_student_credentials()` + `upsert_student()`; lo usan `POST /api/auth/student-login` y `POST /api/registrations/self`. Se eliminó el loopback HTTP y `requests` ya no se importa en `auth_bp`.
- Límites compartidos `CREDENTIAL_ATTEMPT_LIMITS = {"control_number": (8, 300), "ip": (80, 300)}` → **429** con mensaje genérico, aplicados **antes** de llamar al externo (el barrido de números de control desde una misma IP también se frena). Reset para tests: `reset_credential_limits()`.
- Mapeo de errores (antes se devolvía `error: str(e)`, con fuga de detalle): `InvalidCredentials` → **401**, `CredentialServiceUnavailable` → **503**, `CredentialsRateLimited` → **429**.

### 3. Política de estado y de horas

- El self check-in **abre** la sesión: `Attendance.status = "Parcial"` y solo `Registration.attended = True`; ya **no** se cambia `Registration.status` a "Asistió" en la llegada (seguía marcando "Asistió" a quien nunca volvió).
- El cierre (checkout individual o `batch-checkout`) recalcula y sincroniza con `sync_registration_status()`: **`>= 80%` → `Asistió`** (acredita horas), **`< 80%` → `Ausente`** (no acredita: es lo único que quita las horas que `hours_service` da por `Confirmado`), sesión abierta → sin cambios, `Cancelado` → se ignora.
- El dry-run de `batch-checkout` ahora usa el calculador compartido `compute_attendance_metrics` (su copia propia divergía: usaba duración neta en vez de la intersección con la ventana y no aplicaba "pausa >= duración" → predecía 100% donde el cierre real daba < 80%) y expone `details.registration_status` (qué estado quedará en la preregistración).

### 4. Pausas: el cierre descuenta y las varias pausas sí suman

- La pausa abierta **sí descuenta** hasta el check-out: `batch-checkout` / checkout individual dejan de auto-reanudar con duración cero; solo se apaga `is_paused` y `pause_time` se conserva para que el calculador descuente `pause_time → check_out_time`. Antes el alumno que se fue y no volvió cerraba al 100%.
- Cada ciclo pausa/reanuda se **pliega en `check_in_time`** (`resume_attendance`, recortado a la ventana de la actividad) y libera `pause_time`/`resume_time`, de modo que varias pausas sí descuentan (antes la 2ª pausa pisaba el descuento de la 1ª y salía 100%). Sin migración: `created_at` conserva la llegada real.
- La pausa quedó habilitada para `Magistral` **y** `Conferencia` (`SESSION_CONTROL_ACTIVITY_TYPES` en `attendance_service`); la vista de captura para personal sigue siendo solo Magistral.

### 5. Convención de escritura de los tiempos de asistencia (alineación horaria)

- Las columnas `datetime` de MySQL guardan **hora local naive** y así se leen (`safe_iso` / `localize_naive_datetime` interpretan el naive como hora de `APP_TIMEZONE`). Escribir `datetime.now(timezone.utc)` (o `db.func.now()` con el servidor MySQL en UTC) dejaba en la columna una hora **6 h** posterior: al leerla como local el check-in quedaba posterior al inicio de la actividad, la ventana de presencia salía invertida y `calculate_attendance_percentage` devolvía **0%**.
- Bug latente: `batch-checkout` se agregó el 2026-09-28 y **nunca corrió sobre datos reales**; el 46° Aniversario corre 2026-10-05 → 10-09, así que el cierre por lotes habría cerrado el evento al 0%. Evidencia en el dump `EventosTec-2026-10-02-04-33-53.sql` (64 check-ins de la magistral de las 10:00 registrados a las 15:19–15:54 UTC).
- Ahora los instantes que genera el servidor se persisten con **`db_wall_local()` / `db_now_local()`** (`app/utils/datetime_utils.py`) en `attendances_bp` (check-in, check-out y `now` de `batch-checkout`), `registrations_bp` (8 sitios `db.func.now()`), `public_registrations_bp` (walk-in y confirmación), `self_register_bp` (check-in) y `attendance_service` (`pause_time`). Los valores que vienen del payload **no** se convierten: `parse_datetime_with_timezone()` conserva el wall time del cliente (input naive de `<input type="datetime-local">`), igual que `create_activity` ya lo hacía. Detalle y verificación: `docs/TIMEZONE_FIX.md`.
- Sin migración de datos: las filas antiguas escritas en UTC siguen desfasadas 6 h (los eventos cerrados no se re calculan); esto también corrige el desfase de 6 h que mostraba la columna de check-in en la UI.

### 6. Tests

- Nuevos: `tests/api/test_self_register_api.py` (400 faltantes / 404 / ventana no-abierta y cerrada / 401 / 503 / 429 sin volver a llamar al externo / 201 con sesión `Parcial` y preregistro intacto / 409 duplicado / alta de estudiante), `tests/services/test_self_register_service.py`, `tests/services/test_student_auth_service.py` (mapeo de errores y rate-limit por control e IP), `tests/test_datetime_utils_wall_local.py` (round-trip escritura→lectura), `app/static/js/public/__tests__/self_register.test.js` (ventana, countdown con deadline del servidor, ramas 201/401/409/429/400/503/red).
- Actualizados por la nueva política: `tests/api/test_batch_checkout.py` (pausa abierta descuenta + cierre de la preregistro en `Ausente`; dry-run comparte calculador), `tests/api/test_attendances_register.py`, `tests/test_attendance_service.py` (plegado de la pausa, 2ª pausa y no doble descuento), `tests/test_public_slug_views.py`, `tests/api/test_auth_type_claim.py`.
- Resultado de la ronda: **pytest 334 passed / 1 xpassed**, **jest 27 suites / 357 tests**, `ruff check` + `ruff format` + `prettier` limpios en los archivos tocados.
