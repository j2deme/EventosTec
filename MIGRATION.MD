# MIGRATION - Evaluación técnica para migración / refactorización

1. Volumen y complejidad de las vistas actuales

- No. aproximado de templates/pantallas: 28 (carpeta app/templates incluye admin, student, public y auth).

- Pantalla más compleja (interacciones JS): el panel administrativo de Asistencias (app/static/js/admin/attendances.js, ~1510 LOC). Incluye check-ins rápidos, modales, mutaciones in-place, sincronizaciones y operaciones por lotes (batch), por lo que requiere pruebas y coordinación con el backend.

- Componentes reutilizables: sí. app/static/js/app.js expone helpers globales (safeFetch, getAuthHeaders, showToast, dateHelpers). Módulos Alpine (app/static/js/admin/\*.js) siguen patrón factory reutilizable; plantillas parciales en app/templates/admin/partials se usan en múltiples pantallas.

2. Integraciones externas críticas

- Servicio externo de autenticación de alumnos: sí. /api/auth/student-login POST -> <http://apps.tecvalles.mx:8091/api/validate/student> (requests.post). También /api/registrations/self hace llamadas internas al endpoint de login (requests.post a /api/auth/student-login).

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
  - Registro in situ (/api/registrations/self) reutiliza internamente el endpoint /api/auth/student-login (llamada HTTP interna) para validar credenciales antes de crear Attendance.

- Logout (revocado server-side — implementado):
  - POST /api/auth/logout registra el `jti` del token vigente en la tabla `revoked_tokens` (modelo `RevokedToken` en app/models/revoked_token.py + migración alembic `20260927_add_revoked_tokens`, head de `20251031_create_app_settings`) y purga oportunamente las filas de tokens ya vencidos.
  - Flask-JWT-Extended consulta el blocklist en cada request vía `@jwt.token_in_blocklist_loader` (app/__init__.py): un token revocado responde 401 hasta su `exp`; los demás tokens del mismo usuario siguen válidos. Si la migración no se ha aplicado, el loader emite un warning y no bloquea (la app no cae).
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

  - Hallazgo clave para los enlaces (punto 5): `@pre_dump` de `ActivitySchema` copiaba una lista blanca de atributos **sin `public_slug`**, por lo que *ningún* endpoint de actividad devolvía el slug (el `public_url` que agregaba `activities_bp` era código muerto y el modal de enlaces nunca recibía slug). Añadido `public_slug` a la lista blanca → listado, detalle y creación de actividades ahora incluyen `public_slug` (y por tanto `public_url`). Con esto + la auto-generación de slug en create (evento y actividad) + fallback a ID numérico en el modal, el flujo "crear nuevo evento → compartir enlaces con jefes" queda completo.
  - `datetime.utcnow()` (Python 3.14 + `filterwarnings = error::DeprecationWarning:app.*` en pytest.ini) en `settings_manager.py` (2 sitios) y `reports_bp.py` (1) hacía fallar las lecturas de settings en tests: reemplazado por `datetime.now(timezone.utc).replace(tzinfo=None)` (naive-UTC idéntico, patrón ya usado en `revoked_token.py`). Sin este fix, el nuevo default de 60 min se hacía visible como fallo en `test_app_settings_convenience_methods`.
  - Tests reparados (preexistentes, datos/fixtures rotos): `tests/test_activities.py` y `tests/api/test_activities.py` (fechas con offset `-06:00` para superar la validación de rango evento↔actividad con la interpretación naive→APP_TIMEZONE), `tests/test_slug_utils.py` (DummyModel con columna simulada que expone `.like()`), `tests/api/test_public_pause_attendance_timezone.py` (5 tests: `generate_public_token` deprecado → resolución por ID numérico/`activity_id`).
- Despliegue (producción, 2026-09-29): ✅ `flask db upgrade` ejecutado (`alembic_version` reparado a un solo registro en `20260927_add_revoked_tokens`, head). ✅ Seed de settings en BD (4 filas editables: `app_timezone=America/Mexico_City`, `public_pause_available_from_seconds=0`, `public_pause_available_until_after_end_minutes=60`, `public_confirm_window_days=30`). **Pendiente:** desplegar el código nuevo en el servidor con `./deploy.sh` (paso 3) — hasta entonces producción sigue corriendo el código anterior (el logout con blocklist, los fixes de asistencia, los enlaces públicos y la pausa de 60 min solo surten efecto tras el deploy). Smoke-test posterior: Admin → Settings muestra las 4 filas (pausa = 60), logout con token viejo → 401, login de alumno → modal de pausa.

## Créditos complementarios multi-evento (ronda 2026-10-01)

Commits: `2ece1dd` (servicio unificado de horas), `2b2710e` (event_ids), `07d02e2` (exclusión derivada), + el de esta sección (credit_overrides). Tag `v0.9` = última versión en producción (rollback rápido).

- **Fuente única de horas**: `app/services/hours_service.py` — Registration (`Confirmado`/`Asistió`) + Attendance (`Asistió`, walk-ins), dedup por actividad, `round(total, 2)` antes de comparar umbrales (`CREDIT_MIN_HOURS = 10.0`). Los 6 call sites previos (complementary-credits ×2, hours_compliance ×2, hours-by-event, has_credit del detalle) ahora lo usan; se eliminó ~150 líneas duplicadas.
- **Lista de créditos con walk-ins**: la lista del 45° Aniversario pasa de **238 → 518** estudiantes (antes solo consultaba Registrations `Asistió`; `hours_compliance` ya contaba los 3023 pares walk-in). Control post-deploy: `GET /api/students/complementary-credits?event_id=1` debe dar ≈518, consistente con `/api/reports/hours_compliance?event_id=1`.
- **Multi-evento**: `GET /api/students/complementary-credits?event_ids=1,3` (acepta comas y/o repetido; `event_id` simple intacto byte a byte). Respuesta aditiva: `events[]` (orden cronológico), `event: null` en modo multi, `hours_by_event`/`activities_by_event` por estudiante, `excluded_already_credited`, `excluded_by_override`.
- **Exclusión derivada (earliest-crossing)**: con N eventos seleccionados, solo entra quien cruza las 10 h en el **último** evento cronológico; quien cruzó antes ya está acreditado y se omite. Con un solo evento la regla no cambia nada (cruce en el único evento).
- **Overrides manuales**: tabla `credit_overrides` (una fila por estudiante: `decision` include/exclude, `reason`, timestamps). API: `GET/POST /api/students/credit-overrides` (upsert) y `DELETE /api/students/credit-overrides/<student_id>` (admin JWT). `include` fuerza la inclusión aunque falle la regla derivada o no alcance 10 h (incluso sin participaciones → fila sintética con 0 h); `exclude` omite siempre.
- Estado de pruebas: **pytest 236 passed / 0 failed / 0 errors** (+1 xpass preexistente); Jest sin cambios (161 — la UI multi-evento aún no se implementa).

### ⚠️ Paso de despliegue OBLIGATORIO (migración aditiva)

`entrypoint.sh` NO aplica migraciones automáticamente (`AUTO_MIGRATE=false` por defecto). Después de `./deploy.sh`, ejecutar **en el servidor**:

```bash
docker compose exec web flask db upgrade
```

- Nueva revisión: `20261001_add_credit_overrides` (down: `20260927_add_revoked_tokens`). **Solo `CREATE TABLE credit_overrides`** — no altera ni toca tablas existentes (sin riesgo de regresión de datos).
- Mientras no se ejecute, la lista de créditos sigue funcionando: `load_overrides_map()` es defensivo (loguea warning y calcula sin overrides). Los endpoints CRUD de overrides devolverán 500 hasta que la tabla exista — migrar antes de usar esa UI.

### Pendiente documentado (fuera de alcance de esta ronda)

- **Fase 3 (opcional/futura): tabla `credit_grants`** para evitar doble acreditación al re-exportar la lista a la plataforma externa (historial de grants por lote/evento). No implementada a propósito.
- Los overrides solo afectan la lista de créditos (vista admin); el badge del portal del estudiante (`has_complementary_credit` del detalle de evento) sigue puramente derivado.
