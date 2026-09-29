# APP - Informe extendido: Tecnologías, estructura y mapa de endpoints

## Resumen ejecutivo

- Tecnologías: Python 3.13, Flask (Blueprints), Flask-SQLAlchemy, Flask-Migrate/Alembic, Flask-JWT-Extended, Marshmallow (marshmallow-sqlalchemy). Frontend: Jinja2 + Alpine.js + Tailwind (CDN). Tests: pytest (backend), Jest + jsdom (frontend). Utilidades: pandas, openpyxl para reportes, PyMySQL para MySQL, sqids para slugs.

## Estructura clave (carpetas importantes)

- app/api: blueprints REST (auth, events, activities, attendances, registrations, public flows, reports, settings, etc.)
- app/models: modelos SQLAlchemy
- app/schemas: Marshmallow schemas (SQLAlchemyAutoSchema)
- app/services: lógica de negocio (registration_service, attendance_service, settings_manager, etc.)
- app/static/js: frontend JS; app/static/js/admin contiene factories Alpine.js para admin
- app/templates: Jinja2 templates (admin y público)
- migrations/: Alembic/Flask-Migrate

## Decisiones y notas de implementación

- Autenticación: JWT (Flask-JWT-Extended). Tokens guardados en localStorage; interceptor global en app/static/js/app.js inyecta Authorization.
- Serialización y validación: Marshmallow (schemas centralizados). Muchos endpoints usan .load()/.dump() y SQLAlchemyAutoSchema.
- Compatibilidad de DB: sqlite por defecto en dev, soporta MySQL (pymysql) en producción; configuraciones en config.py.
- Settings dinámicos: SettingsManager/AppSetting con jerarquía ENV -> DB+cache -> default.
- Tests frontend: módulos JS capturan fetch/localStorage al cargar; tests deben mockear antes de require() y usar jest.resetModules().

## Mapa de endpoints (extracto por blueprint)

Nota: lista basada en los blueprints en app/api.

1. Autenticación (Blueprint: /api/auth)

- POST /api/auth/login
  - Login administradores. Body: { username, password } -> devuelve access_token y user.
- POST /api/auth/student-login
  - Login estudiantes. Valida contra servicio externo; crea/actualiza Student y devuelve access_token + student.
- GET /api/auth/profile?type=student|admin
  - Perfil del usuario actual (JWT required). Para student devuelve student, para admin devuelve user.
- POST /api/auth/logout (JWT required)
  - Logout (cliente elimina token).

2. Eventos (Blueprint: /api/events)

- GET /api/events/ (paginado, filtros: page, per_page, status, search, sort)
- POST /api/events/ (JWT + admin) -> crea evento; genera public_slug si falta
- GET /api/events/<int:event_id>
- PUT /api/events/<int:event_id> (JWT + admin)
- DELETE /api/events/<int:event_id> (JWT + admin)
- GET /api/events/<int:event_id>/public-token (JWT + admin) -> genera token público y url
- GET /api/events/<int:event_id>/activities -> lista actividades del evento
- GET /api/events/<int:event_id>/departments

3. Actividades (Blueprint: /api/activities)

- Endpoints CRUD para actividades (list, create, get, update, delete)
- Upload/import helpers y endpoints relacionados con sincronización y manipulación masiva (ver app/api/activities_bp.py para rutas exactas).

4. Inscripciones / preregistros (Blueprint: /api/registrations)

- CRUD y consultas de preregistros. Soporta query params y synth option (synth=1) para datos sintetizados.
- Endpoints para confirmar, cancelar y ver detalles del preregistro.

5. Asistencias (Blueprint: /api/attendances)

- Endpoints para check-in/check-out, sincronizaciones y batch operations.
- POST /api/attendances/sync-related (body: { source_activity_id, student_ids|null, dry_run })
- POST /api/attendances/batch-checkout (body: { activity_id, dry_run })
- Rutas para listar asistencias, filtrar por actividad/fecha y exportar reportes (Excel/CSV).

6. Público - preregistros y eventos públicos

- GET /public/event/<event_slug> (render template público del evento)
- POST /api/public/event/<event_ref>/activity-slug -> devuelve activity_slug y event_slug (útil para rutas públicas)
- Public registrations blueprint (public registration forms + endpoints para listar/descargar registros públicos)

7. Registro in situ (Blueprint: self-register; prefijos mixtos)

- GET /self-register y /public/self-register/<path:activity_ref> -> formulario público
- POST /api/registrations/self -> API para registro in situ (valida credenciales llamando internamente /api/auth/student-login, crea Student si no existe, crea Attendance)

8. Estudiantes (Blueprint: /api/students)

- Endpoints para CRUD estudiantes, búsquedas, y utilidades (export, estadísticas relacionadas).

9. Reportes (Blueprint: /api/reports)

- Endpoints para generar reportes (Excel/Pandas/openpyxl). Soporta render_template o Response con archivos.

10. Estadísticas (Blueprint: /api/stats)

- GET /api/stats/ -> estadísticas generales: total_activities, total_registrations, total_attendances, today_attendances, total_students, active_events.

11. Configuración admin (Blueprint: /admin/api/settings)

- GET /admin/api/settings (JWT + admin) -> lista settings (debug info opcional)
- GET /admin/api/settings/{key} (JWT + admin)
- PUT /admin/api/settings/{key} (JWT + admin) -> update (value and/or description) via SettingsManager (validación & locking)
- POST /admin/api/settings/{key}/reset (JWT + admin) -> reset to default

12. Endpoints públicos auxiliares

- Rutas para assets públicos y vistas: templates en app/templates/public (self_register.html, pause_attendance.html, etc.)

Observaciones de seguridad y compatibilidad

- JWT: tokens en localStorage — asegurarse de usar HTTPS en producción.
- Calls a external auth service (student-login) may introduce latency/failures: endpoints manejan timeouts y códigos 401/503.
- Interceptor de fetch en app/static/js/app.js modifica global.fetch en carga: tests deben adaptarse.
- Settings pueden ser bloqueadas por ENV; la API refleja esto en is_locked_by_env/is_editable.
- Soporte de DB: sqlite para dev, MySQL en producción. Configuración flexible en config.py y manejo de dependencias (pymysql).
