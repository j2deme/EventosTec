# Instrucciones para agentes AI — EventosTec

Breve y práctica: estas notas ayudan a un agente a ser productivo rápidamente en este repositorio.

- Stack principal: Python 3.13 + Flask + SQLAlchemy + Marshmallow (backend). Frontend: Alpine.js + Tailwind (templates en Jinja2). Tests: pytest (backend) y Jest/jsdom (frontend JS).

## Estructura clave

- `app/` — aplicación Flask: `api/`, `models/`, `services/`, `schemas/`, `templates/`, `static/`.
- `app/static/js/` — JS del frontend. Código admin en `app/static/js/admin/` (p. ej. `dashboard.js`, `activities.js`, `attendances_list.js`). Código compartido en `app/static/js/app.js`.
- `app/templates/` — plantillas Jinja2. Código admin en `app/templates/admin/partials/` (p. ej. `dashboard.html`, `activities.html`, `attendances.html`, `registrations.html`).
- `tests/` — tests backend (pytest) organizados por módulos; tests frontend (Jest) en `app/static/js/admin/__tests__/`.

## Patrón de módulos frontend (Alpine factories):

- Cada archivo bajo `app/static/js/admin/` exporta una función factory que devuelve el estado/metodos usados por Alpine (ej: `function attendancesList(){ return { ... }}`) y además se expone para Node via `module.exports` o se adjunta a `window` para el navegador.
- Consecuencia: muchos módulos ejecutan inicialización al ser requeridos (p. ej. el interceptor global de `fetch` en `app/static/js/app.js`). Tests deben preparar `global.fetch` o `localStorage` _antes_ de requerir el módulo si esperan que el módulo capture esas referencias en tiempo de carga.

## Interceptor global de fetch (`app/static/js/app.js`):

- Al cargar `app.js` se captura `window.fetch` (si existe) y se reemplaza por una función que agrega `Authorization` y `Content-Type` cuando procede.
- Recomendación para tests: ver la sección "Tests frontend" abajo para la forma recomendada de mockear `fetch` y usar `jest.resetModules()` cuando el módulo captura referencias en carga.

## Autenticación y tokens:

- `authToken` y `userType` se almacenan en `localStorage`. Helpers útiles expuestos en `app.js`: `getAuthToken()`, `getAuthHeaders(additional)`, `isAuthenticated()`, `checkAuthAndRedirect()`.
- `isAuthenticated()` decodifica el payload de un JWT simple (base64) y elimina token si está corrupto o expirado.

## Tests frontend (Jest + jsdom) — puntos críticos:

- Cargar módulos que leen `localStorage` o interceptan `fetch` requiere preparar `global.localStorage` y `global.fetch` antes de `require()` del módulo. Usa `jest.resetModules()` entre escenarios donde el módulo debe capturar referencias distintas.
- jsdom no implementa navegación real (window.location.href puede lanzar 'Not implemented: navigation'); tests que manipulan `window.location` deben definir `Object.defineProperty(window, 'location', ...)` con un objeto simulado si van a cambiar `href`.
- Cuando un test comprueba que el interceptor añadió headers, acepta varias posiciones: algunos mocks ponen headers en `init.headers`, otros esperan `init.Authorization` — los tests del repo ya usan comprobaciones tolerantes (revisar `app.static/js/__tests__/app.coverage.test.js`).

Ejemplo (Jest + jsdom) — mockear `fetch` antes de requerir `app.js`:

```javascript
// resetear módulos para que el require capture nuestro mock
jest.resetModules();

// mockear global.fetch antes de require
const calls = [];
global.fetch = jest.fn((input, init) => {
  calls.push({ input, init });
  return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
});

// requerir app.js para que el interceptor capture `global.fetch`
require("../app");

// configurar token que el interceptor deberá inyectar
window.localStorage.setItem("authToken", "TOKEN123");

// llamar a fetch y comprobar que el mock recibió headers
await window.fetch("/api/x", { method: "GET" });

expect(
  calls[0].init?.headers?.Authorization || calls[0].init?.Authorization
).toBe("Bearer TOKEN123");

// limpieza: resetear módulos y eliminar el mock si hace falta
jest.resetModules();
delete global.fetch;
require("../app");
```

## Comandos útiles (desarrollo y pruebas):

- Instalar dependencias Python: `pip install -r requirements.txt`
- Ejecutar servidor dev Flask: `flask run` o `python run.py`
- Migraciones: `flask db migrate -m "..."` y `flask db upgrade`
- Ejecutar tests backend: `python -m pytest -q`
- Ejecutar tests frontend (desde workspace root): `npx jest --coverage --colors`

## Contribuir cambios al frontend JS:

- Evita modificar `app/static/js/app.js` sin considerar efectos en tests (interceptor y helpers globales). Si cambias cómo se instala el interceptor, actualiza los tests asociados — ver la sección "Tests frontend" para recomendaciones de mocking y `jest.resetModules()`.
- Para agregar nuevas utilidades compartidas, exponerlas en `app/static/js/app.js` (window) y documentarlas en README.
- Si realizas cambios en el frontend JS que afectan a la interfaz o al comportamiento, actualiza o añade tests Jest en `app/static/js/admin/__tests__/` que cubran el nuevo comportamiento. Mockear `fetch` y `localStorage` según sea necesario.
- Si agregas nuevos endpoints o cambias contratos JSON, actualiza los tests Jest que consumen esos endpoints y asegúrate de que los mocks reflejen el nuevo contrato.
- Si el cambio afecta exclusivamente a la UI (p. ej. HTML/CSS en plantillas Jinja2), puedes omitir tests Jest y tests pytest, pero documenta el cambio en la descripción del PR.

## Convenciones específicas notables:

- Los módulos que se usan tanto en el navegador como en Jest exportan una factory y también se exponen en `window` para el runtime del navegador (mirar `attendances_list.js` y otros archivos en `admin/`).
- Tests de integración del frontend se agrupan bajo `app/static/js/admin/__tests__/` y frecuentemente mockean `fetch` y servicios con `jest.fn()`.

## Archivos importantes a revisar para comprender flujo y edge-cases:

- `app/static/js/app.js` — helpers globales, interceptor, showToast
- `app/api/*_bp.py` — Blueprints REST: ver contratos (payloads/responses) que frontend espera
- `app/services/*_service.py` — lógica de negocio reutilizable
- `app/models/*.py` — modelos SQLAlchemy y relaciones
- `app/schemas/*.py` — Marshmallow schemas y validaciones
- `app/templates/admin/partials/*.html` — plantillas Jinja2 del admin
- `app/static/js/admin/*.js` — módulos JS del admin (Alpine factories)

## Errores y señales comunes en runs de tests:

- Recursión/stack overflow al mockear `fetch` puede ocurrir si el mock se instala después de que el módulo ya reemplazó `window.fetch`; ver la sección "Tests frontend" para la mitigación (mock antes de require + `jest.resetModules()`).
- `TypeError: _fetch is not a function` aparece si `app.js` capturó una referencia no-función a `fetch`. Asegurar que `global.fetch` es una función en tests.

## Preguntas que un agente debe hacer si recibe ambigüedad:

- ¿Quieres que los cambios de frontend mantengan retrocompatibilidad con la forma en que los tests mockean `fetch` (captura en carga) o podemos cambiar el patrón para usar un helper explícito (p. ej. `setFetchForTests`) y actualizar tests en bloque?
- Si algo no queda claro, dime qué sección quieres ampliar (por ejemplo: ejemplos concretos de tests con `jest.resetModules()` + mock de `fetch`, o fragmentos de `app.js` que deben documentarse).

## Cambios en modelos/schemas y endpoints

- Cada vez que se implemente un cambio en los modelos y/o schemas del backend, se deben revisar los endpoints asociados y actualizarlos para reflejar esos cambios, sin romper las funciones ya implementadas cuando sea posible. Específicamente:

  - Revisar todos los endpoints que lean o escriban las entidades afectadas y ajustar la serialización/deserialización (Marshmallow schemas) según el nuevo contrato.
  - Priorizar compatibilidad hacia atrás. Si el cambio es breaking, documentarlo claramente y considerar versionar el endpoint (por ejemplo `/api/v2/...`) antes de remover el comportamiento anterior.
  - Actualizar la validación de entrada y los manejadores de errores para los nuevos campos o formatos.

- Si cambia o se actualiza un endpoint, hay que actualizar los tests relacionados y validar la suite completa:

  - Ajustar los tests unitarios y de integración que dependen del endpoint. Si los tests frontend consumen ese endpoint, actualizarlos también (Jest/jsdom + mocks de `fetch`).
  - Añadir tests nuevos cuando se introduzcan nuevas responsabilidades, transformaciones de payload o reglas de negocio.
  - Ejecutar `python -m pytest -q` para validar los tests backend y `npx jest --coverage --colors` para los tests frontend. Corregir regresiones antes de mergear.

- Checklist sugerido antes de mergear cambios en modelos/schemas/endpoints:
  - [ ] Actualizar modelos y schemas (si aplica).
  - [ ] Revisar y actualizar los endpoints que usan las entidades.
  - [ ] Actualizar o añadir tests backend (pytest).
  - [ ] Actualizar o añadir tests frontend (Jest) y mocks (mockear `fetch` y/o `localStorage` antes de require si el módulo captura referencias en carga).
  - [ ] Ejecutar suites de tests (backend y frontend) y revisar cobertura.
  - [ ] Documentar breaking changes y versionar endpoint si es necesario.

## Sincronía entre endpoint, interfaz y scripts JS

Cuando se realizan cambios en modelos/schemas o en el contrato de un endpoint, es crítico asegurar que la interfaz (templates y componentes JS) y los scripts que consumen ese endpoint estén actualizados y sincronizados. Esta sección describe un flujo práctico y un checklist para minimizar regresiones.

Flujo práctico:

- 1. Detectar alcance del cambio: identificar qué endpoints cambian (nombres de campos, estructura del JSON, rutas, parámetros query/path) y qué consumidores existen (plantillas Jinja2, módulos JS en `app/static/js/`, tests frontend).
- 2. Establecer compatibilidad hacia atrás: si el cambio puede romper clientes existentes, considerar mantener soporte temporal (p. ej. aceptar ambas formas `data` y `attendances`) o versionar el endpoint (`/api/v2/...`) hasta que todos los consumidores estén migrados.
- 3. Actualizar backend: aplicar cambios a modelos/schemas y endpoints. Añadir transformaciones/serializadores que faciliten compatibilidad si es necesario.
- 4. Actualizar contratos y documentación: actualizar cualquier documentación interna (comentarios en el código, README, `copilot-instructions.md`) y generar un pequeño ejemplo de payload esperado.
- 5. Actualizar tests backend: adaptar y añadir tests unitarios/integración que validen el nuevo contrato.
- 6. Actualizar scripts y templates frontend:
  - Buscar todos los lugares que consumen el endpoint (grep por la ruta o por nombres de funciones en `app/static/js/` y templates).
  - Actualizar parsing y mapeo en los módulos JS. Prefiere parseos tolerantes cuando la forma puede variar (ej. aceptar `resp`, `resp.attendances` o `resp.data`).
  - Si el endpoint cambia nombre o parámetros, actualizar las llamadas `fetch()` y cualquier helper de construcción de URLs en `app/static/js/app.js` o módulos relacionados.
- 7. Actualizar tests frontend: añadir/ajustar mocks de `fetch` (mockear antes de require + `jest.resetModules()` si el módulo captura referencias en carga) y actualizar asserts en templates o factories.
- 8. Ejecutar suites completas: `python -m pytest -q` y `npx jest --coverage --colors`. Corregir regresiones hasta que ambas suites pasen.
- 9. Revisar y desplegar: si hay cambios breaking, documentar en release notes y coordinar despliegue (backend primero si mantiene compatibilidad, o frontend y backend juntos si hay versionado).

Checklist mínimo antes de mergear (aplicable a PRs que modifican endpoints o modelos relacionados con frontend):

- [ ] Listado de endpoints modificados y ejemplo(s) de request/response han sido añadidos a la descripción del PR.
- [ ] Backend: modelos/schemas y endpoints actualizados y cubiertos por tests unitarios o de integración.
- [ ] Frontend: todos los módulos JS y templates que consumen el endpoint han sido identificados y actualizados.
- [ ] Frontend tests actualizados: mocks de `fetch` y `localStorage` actualizados; pruebas que requieren capturar mocks en carga usan `jest.resetModules()`.
- [ ] Si no se puede mantener compatibilidad, el endpoint ha sido versionado o el PR documenta claramente el plan de migración.
- [ ] Ejecución local de ambas suites de tests (backend y frontend) completada y sin regresiones.

Notas y buenas prácticas:

- Centraliza las utilidades de construcción de URLs y headers en `app/static/js/app.js` cuando sea posible; así las actualizaciones de parámetros/headers son menos propensas a quedarse desincronizadas.
- Cuando el cambio es mayor, crear una pequeña prueba de contrato end-to-end (por ejemplo, un test de integración backend que produce el payload y un test frontend que consuma ese mismo mock) para validar la interpretación del contrato en ambos lados.
- Para cambios pequeños (nombres de campo), preferir introducir adaptadores (p. ej. mapear `oldName` → `newName`) en el backend o en una capa de parsing del frontend durante el período de migración.
- Asegurar que la documentación del PR incluya ejemplos concretos de payload y un checklist de qué revisar en frontend.

Seguir este proceso evita regresiones y mantiene consistencia entre backend y frontend cuando evoluciona el modelo de datos.
