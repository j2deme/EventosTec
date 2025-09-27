# AGENTS.md — Guía para agentes LLM trabajando en el repositorio EventosTec

Propósito

Este documento es una referencia práctica para LLMs (agentes) que contribuyen a este repositorio. Contiene convenciones, archivos clave, flujos de trabajo seguros y ejemplos de tareas recurrentes para que las ediciones sean consistentes, probadas y de bajo riesgo.

Resumen del proyecto

- Stack: Python 3.x (Flask) + SQLAlchemy + Marshmallow en backend. Frontend con Jinja2 + Alpine.js + Tailwind. Tests: pytest (backend) y Jest/jsdom (frontend).
- Ubicación principal del código fuente: `app/`.

Reglas generales que debe seguir un agente

1. Siempre leer los archivos relevantes antes de editar.
2. Antes de cualquier cambio, crear o actualizar la lista de TODOs con `manage_todo_list` y marcar exactamente UNA tarea como `in-progress`.
3. Hacer cambios pequeños y autocontenidos. Preferir aplicar parches mínimos y atómicos.
4. Ejecutar pruebas relevantes localmente (backend con pytest, frontend con jest) después de cambios significativos. Si no es posible ejecutar jest, al menos ejecutar pytest para validar backend.
5. No exfiltrar secretos ni modificar archivos en `instance/` o `venv/`.
6. No ejecutar llamadas de red externas que no sean necesarias. Si el cambio requiere credenciales o servicios externos, explicar la limitación y proponer alternativas.
7. Si se crea o cambia un endpoint público o contrato JSON, documentar el cambio y añadir tests que cubran el nuevo comportamiento.
8. Si la edición afecta a frontend JS que instala un interceptor global (por ejemplo `app/static/js/app.js`), actualizar/añadir tests Jest que mockeen `fetch` y `localStorage` _antes_ de requerir el módulo (usar `jest.resetModules()`).

Archivos y rutas clave

- `app/api/registrations_bp.py` — endpoints para preregistros (`/api/registrations`). Contiene lógica de síntesis (`synth`) en el detalle.
- `app/static/js/app.js` — interceptor global de `fetch`, helpers `getAuthToken()`, `getAuthHeaders()`, `isAuthenticated()`.
- `app/static/js/admin/attendances.js` — factory `attendancesAdmin()` con la UI admin (modales, sync, batch, openRegistrationModal).
- `app/templates/admin/partials/attendances.html` — plantilla Jinja2 que usa la factory Alpine y contiene modales mencionados.
- `app/services/` — lugar recomendado para extraer lógica reutilizable del backend (por ejemplo `synth` extraction).
- `tests/` — tests backend (pytest) organizados por módulos; `app/static/js/admin/__tests__` contiene tests Jest para frontend.

Contratos y convenciones JSON importantes

- `GET /api/registrations/<id>`:
  - Respuesta por defecto: `{ registration: <object> }` (anidado, serializado por Marshmallow).
  - Con `?synth=1`: respuesta adicional `synthesized: { registration_id, student_name, student_identifier, email, activity_name, event_name, ... }`.
- `POST /api/attendances/sync-related`:
  - Body esperado: `{ source_activity_id, student_ids: [ids]|null, dry_run: boolean }`.
  - Si `student_ids === null`, backend debe interpretar que sincronice todos desde la actividad fuente.
- `POST /api/attendances/batch-checkout`:
  - Body: `{ activity_id, dry_run: boolean }`.

Pruebas y validación rápida

- Backend (pytest):
  - Ejecutar: `${workspaceFolder}\venv\Scripts\python.exe -m pytest -q` (task disponible en VS Code tasks).
  - Priorizar tests: `tests/services`, `tests/api`, `tests/utils` cuando cambies lógica de negocio.
- Frontend (Jest):
  - Ejecutar: `npx jest --colors --runInBand "app/static/js/admin/__tests__"`.
  - Recordatorio: mockear `global.fetch` y `global.localStorage` antes de `require()` si el módulo captura referencias en la carga; usar `jest.resetModules()` entre escenarios.

Cómo crear cambios seguros (checklist de cambios)

1. Leer los archivos relevantes.
2. Abrir la lista TODO y marcar una tarea `in-progress`.
3. Hacer edits mínimos con `apply_patch` o `insert_edit_into_file`.
4. Ejecutar `pytest` (y `jest` si tocaste frontend) para validar.
5. Reparar errores y re-ejecutar pruebas hasta pasar o hasta 3 iteraciones de corrección automática.
6. Cerrar la tarea en la lista TODO como `completed` y añadir notas de verificación.

Plantillas y snippets útiles

- PR description minimal:

  - Qué cambia: (breve resumen)
  - Archivos modificados: (lista)
  - Tests añadidos: (si aplica)
  - Cómo probar localmente: pasos concretos (ejecutar server, endpoints, UI flows)

- Ejemplo de test unitario backend (pytest) para `synth`:

  - Crear un test que cargue un `Registration` serializado y verifique que `GET /api/registrations/<id>?synth=1` retorna `synthesized` con keys esperadas.

Tareas comunes y cómo abordarlas

1. "El modal muestra vacío":
   - Verificar si frontend depende de `flattenRegistrationData()` o de `synth`. Si hay un stub (devuelve `null`), preferir usar `?synth=1` del backend o reimplementar flatten.
2. "Formalizar synth en backend":
   - Extraer la construcción del objeto sintetizado a `app/services/registration_service.py` con función `build_synth_for_registration(registration_serialized)`.
   - Añadir tests unitarios que validen fields y valores nulos.
3. "Re-implementar flattenRegistrationData":
   - Reescribir la función en `attendances.js` para que acepte tanto objetos anidados como arrays y devuelva un objeto plano.
   - Añadir tests Jest que requieran el módulo después de mockear `fetch` y `localStorage`.
4. "Batch checkout dry-run muestra errores por fila":
   - Ampliar la respuesta del endpoint con `summary` y `details` por fila. Actualizar el template HTML para renderizar `details`.

Seguridad y privacidad

- Nunca incluir tokens, contraseñas o archivos en el repo.
- No exponer `instance/test_eventostec.db` ni información sensible. Si necesitas datos de ejemplo, crear fixtures de tests en `tests/fixtures`.

Errores comunes y cómo detectarlos

- `TypeError: _fetch is not a function` al ejecutar tests: ocurre si `app.js` capturó una referencia no-función a `fetch`. Fix: mockear `global.fetch = jest.fn()` antes de requerir el módulo y usar `jest.resetModules()` después.
- Pylance warnings sobre `.get` en objetos no-dict: normalizar (convertir) la estructura en dicts antes de usar `.get` o añadir helpers `as_dict()`.

Notas finales

- Mantén el cambio backward-compatible cuando edites endpoints públicos; si no es posible, versiona (por ejemplo `/api/v2/...`).
