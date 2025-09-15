# Eventos Tec

Sistema de control de asistencias para institución educativa.

## Estado del proyecto (actualizado: 13 de septiembre de 2025)

El proyecto está en estado de desarrollo activo. Las siguientes funcionalidades importantes están implementadas y disponibles en la rama `main`:

- API RESTful con Flask + SQLAlchemy + Marshmallow
- Autenticación basada en JWT para endpoints administrativos
- Gestión de eventos, actividades y estudiantes
- Sistema de relaciones entre actividades (enlace bidireccional)
- Dashboard administrativo con páginas para eventos, actividades y reportes
- Gestión de pre-registros (registros de estudiantes en actividades) desde el dashboard administrativo (interfaz y lógica completa)

Se han añadido también mejoras en estadísticas y endpoints auxiliares para soportar el dashboard.

## Instalación y ejecución rápida

1. Crear y activar un entorno virtual:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1    # PowerShell (Windows)
# o en cmd.exe: venv\Scripts\activate
```

2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3. Configurar variables de entorno (copiar ejemplo y editar `.env` según tu entorno):

```powershell
copy .env.example .env
```

4. Inicializar la base de datos (si es necesario):

```powershell
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

5. Ejecutar la aplicación en modo desarrollo:

```powershell
flask run
# o: python run.py
```

## Cómo verificar rápidamente (sanity check)

Desde el workspace puedes comprobar que la aplicación se importa correctamente (esto no inicia el servidor):

```powershell
python -c "from app import create_app; app = create_app(); print('OK: aplicación importada')"
```

## Pruebas

Se incluyen pruebas con `pytest`. Para ejecutar el suite de tests:

```powershell
pip install -r requirements.txt  # asegura pytest instalado
python -m pytest -q
```

Para ejecutar pruebas específicas:

```powershell
python -m pytest app/tests/test_registrations.py -q
```

## Cambios recientes relevantes

Las implementaciones más relevantes realizadas recientemente son:

- Gestión de pre-registros en el dashboard administrativo:

  - Template: `app/templates/admin/partials/registrations.html`
  - Lógica frontend: `app/static/js/admin/registrations.js`
  - Integración en dashboard: `app/templates/admin/dashboard.html`, `app/static/js/admin/dashboard.js`, `app/templates/admin/base.html`
  - Documentación interna: `REGISTROS_ADMIN.md`

- Mejora de estadísticas (endpoint): `app/api/stats_bp.py` (incluye métricas útiles para el dashboard)

Otros cambios menores y correcciones en módulos relacionados con actividades, relaciones entre actividades y manejo de errores.

## Estructura (resumen)

- `app/` - Aplicación principal
  - `api/` - Blueprints REST (events, activities, registrations, students, stats, etc.)
  - `models/` - Modelos SQLAlchemy
  - `templates/` - Plantillas Jinja2 (incluye `admin/partials` con componentes del dashboard)
  - `static/js/admin/` - JavaScript del dashboard (Alpine.js)

## Puntos pendientes y siguientes pasos sugeridos

1. Resolver discrepancias en estadísticas que se muestran en el dashboard (se detectó inconsistencia entre datos y vistas en un caso concreto).
2. Añadir exportación de registros (CSV/Excel) y reportes por actividad/evento.
3. Mejorar tests de integración end-to-end para flujos administrativos (crear/confirmar/asistir/cancelar).
4. Añadir historial de cambios (audit log) para acciones administrativas.

Si quieres que haga alguno de estos puntos ahora (por ejemplo: exportar registros o añadir tests de integración), dime cuál y lo implemento.

## Recursos y contacto

Consulta el resto de la estructura del proyecto en la carpeta `app/`. Si necesitas ayuda para desplegar en producción o configurar la base de datos MySQL, indícamelo y preparo una guía de despliegue.

## Mocking de fetch y `safeFetch` (Jest)

Nota breve: se centralizó la lógica HTTP en un helper global `safeFetch` (`app/static/js/app.js`) que agrega headers de autorización y Content-Type. Para prevenir una recursión accidental en el navegador (cuando `window.fetch` es reemplazado por un wrapper), `safeFetch` prioriza la referencia original a `fetch` capturada al cargar el módulo. Esto afecta la forma en que los tests pueden espiar o mockear `fetch`.

Ejemplos de cómo mockear en Jest (en español):

- Mockear `global.fetch` antes de requerir el módulo (recomendado cuando el test necesita que el interceptor capture el mock):

```javascript
// test.js
jest.resetModules(); // importante para que el require recapture mocks

// instalar mock antes de require
global.fetch = jest.fn((input, init) =>
  Promise.resolve({ ok: true, json: () => Promise.resolve({ data: [] }) })
);

const adminModule = require("../admin/activities");
// ahora las llamadas dentro de adminModule usarán el mock

test("usa global.fetch", async () => {
  await adminModule.loadActivities();
  expect(global.fetch).toHaveBeenCalled();
});
```

- Mockear `window.safeFetch` directamente (recomendado cuando quieres controlar la inyección de headers o tests más aislados):

```javascript
// test_safeFetch.js
const safeFetchMock = jest.fn(() =>
  Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
);
window.safeFetch = safeFetchMock;

const adminModule = require("../admin/events");

test("usa window.safeFetch", async () => {
  await adminModule.loadEvents();
  expect(window.safeFetch).toHaveBeenCalled();
});
```

- Notas rápidas:
  - Si mockeas `global.fetch` después de requerir `app/static/js/app.js`, ten en cuenta que `safeFetch` podría estar usando la referencia original a `fetch` tomada en carga; por eso la estrategia de `jest.resetModules()` + mock antes de require es la más robusta.
  - Otra opción es mockear `window.safeFetch` en lugar de `fetch` si quieres evitar tocar la captura inicial.
  - La implementación actual prioriza seguridad en runtime (evitar recursión en navegador). Si decides cambiar a un modelo donde `safeFetch` delegue siempre en `global.fetch`, habrá que actualizar tests y la documentación.

Si quieres, puedo añadir un archivo `app/static/js/TESTING.md` con esos ejemplos y más patrones usados en este repo (por ejemplo, cómo mockear `localStorage` y `Toastify` en jsdom).
