# Eventos Tec

Eventos Tec es una aplicación web para la gestión integral de eventos académicos, orientada a instituciones educativas que requieren organizar, monitorear y reportar la participación estudiantil en conferencias, talleres, cursos y actividades magistrales.

## Características principales

- **Dashboard administrativo**: Permite a administradores y organizadores crear, editar y gestionar eventos y actividades asociadas.
- **Calendario interactivo**: Visualización de actividades por día y horario, facilitando la planificación y consulta rápida.
- **Gestión de preregistros y asistencias**: Herramientas para revisar preregistros, confirmar asistencias y generar reportes de participación.
- **Portal para estudiantes**: Espacio dedicado donde los estudiantes pueden consultar eventos disponibles, ver detalles y gestionar sus preregistros.

## Tecnologías utilizadas

- **Backend**: Python 3.13, Flask, SQLAlchemy, Marshmallow.
- **Frontend**: Alpine.js, Tailwind CSS, Jinja2 templates.
- **Testing**: pytest (backend), Jest + jsdom (frontend JS).

## Estructura del proyecto

```bash
app/
  api/           # Blueprints REST (endpoints)
  models/        # Modelos de datos SQLAlchemy
  services/      # Lógica de negocio
  schemas/       # Serialización/deserialización (Marshmallow)
  templates/     # Plantillas Jinja2
  static/
    js/          # Código JS frontend
      admin/     # Módulos Alpine.js para administración
      app.js     # Utilidades y helpers globales
```

## Instalación y ejecución

Las instrucciones siguientes están adaptadas para entornos Windows (PowerShell). Ajusta los comandos si usas Linux/macOS.

1. Crear y activar un entorno virtual (recomendado):

   PowerShell:

   ```powershell
   python -m venv venv; .\venv\Scripts\Activate.ps1
   ```

2. Instalar dependencias Python:

   ```powershell
   pip install -r requirements.txt
   ```

3. Ejecutar el servidor de desarrollo (opciones):
   - Usando el helper `run.py` (recomendado en desarrollo local):

   ```powershell
   .\venv\Scripts\python.exe .\run.py
   ```

   - O con Flask directamente (establecer variables de entorno primero):

   ```powershell
   $Env:FLASK_APP = 'run.py'; $Env:FLASK_ENV = 'development'; .\venv\Scripts\python.exe -m flask run
   ```

4. Ejecutar tests backend (pytest):

   ```powershell
   .\venv\Scripts\python.exe -m pytest -q
   ```

5. Ejecutar tests frontend (Jest):

   ```powershell
   npx jest --coverage --colors
   ```

Si usas Linux/macOS (bash), los comandos equivalentes son:

```bash
python3 -m venv venv; source venv/bin/activate
pip install -r requirements.txt
python3 run.py
# o
FLASK_APP=run.py FLASK_ENV=development python3 -m flask run
python3 -m pytest -q
npx jest --coverage --colors
```

## Contribución

- Revisa las [instrucciones para agentes AI](.github/copilot-instructions.md) y `AGENTS.md` para detalles sobre el stack, patrones de módulos JS y buenas prácticas de testing y cambios.
- Antes de modificar endpoints, modelos o schemas, actualiza los tests y documenta cambios breaking; si es necesario, versiona el endpoint (por ejemplo `/api/v2/...`).
- Para cambios en frontend JS, ten en cuenta que `app/static/js/app.js` instala un interceptor global de `fetch`; los tests Jest deben mockear `global.fetch` y `global.localStorage` antes de `require()` del módulo y usar `jest.resetModules()` entre escenarios.

Notas rápidas y recomendaciones:

- Base de datos de ejemplo: `instance/test_eventostec.db` se incluye para pruebas locales; no subir información sensible.
- Comandos útiles (ya configurados como tareas en VS Code):
  - "Run pytest (venv)": ejecuta `pytest` usando el intérprete del venv.
  - "Run Flask (venv)": ejecuta `run.py` con el intérprete del venv.
  - "Run Jest (frontend)": ejecuta las pruebas Jest para `app/static/js/admin/__tests__`.
- Si modificas el interceptor global en `app/static/js/app.js`, actualiza los tests Jest que dependen de su comportamiento.

## Licencia

Este proyecto se distribuye bajo los términos definidos por la institución. Consulta el archivo LICENSE para más detalles.

## Contacto

Para soporte o sugerencias, contacta al equipo de desarrollo o abre un issue en el repositorio.
