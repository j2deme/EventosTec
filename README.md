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

1. Instala dependencias Python:
   ```
   pip install -r requirements.txt
   ```
2. Ejecuta el servidor de desarrollo:
   ```
   flask run
   ```
3. Ejecuta tests backend:
   ```
   python -m pytest -q
   ```
4. Ejecuta tests frontend:
   ```
   npx jest --coverage --colors
   ```

## Contribución

- Revisa las [instrucciones para agentes AI](.github/copilot-instructions.md) para detalles sobre el stack, patrones de módulos JS y buenas prácticas de testing.
- Antes de modificar endpoints, modelos o schemas, asegúrate de actualizar los tests y documentar cambios breaking.
- Para cambios en frontend JS, considera los efectos en los tests y sigue las convenciones de exportación y mocking descritas en la documentación interna.

## Licencia

Este proyecto se distribuye bajo los términos definidos por la institución. Consulta el archivo LICENSE para más detalles.

## Contacto

Para soporte o sugerencias, contacta al equipo de desarrollo o abre un issue en el repositorio.
