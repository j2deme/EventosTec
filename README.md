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
