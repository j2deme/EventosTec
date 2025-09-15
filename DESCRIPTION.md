# **Resumen del Proyecto: "Eventos Tec"**

## **1. Descripción General**

Una aplicación web para gestionar y controlar la asistencia de estudiantes a eventos académicos (conferencias, talleres, cursos, actividades magistrales) en una institución educativa. Los estudiantes pueden preregistrarse y registrar su asistencia, mientras los administradores gestionan eventos, actividades y generan reportes.

## **2. Tecnologías Utilizadas**

- **Backend:** Python 3.13
- **Framework Web:** Flask
- **Base de Datos:** MariaDB (con uso de SQLite en pruebas)
- **ORM:** SQLAlchemy 2.0
- **Serialización:** Marshmallow
- **Autenticación:** JWT (Flask-JWT-Extended)
- **Testing:** Pytest
- **Frontend:** HTML, Tailwind CSS (CDN), Alpine.js (CDN), Tabler Icons (CDN)
- **Gestión de Migraciones:** Flask-Migrate (Alembic)

## **3. Estado Actual del Desarrollo**

- **✅ Fase 1: Análisis y Diseño:** Completada. Se definieron entidades, relaciones y reglas de negocio.
- **✅ Fase 2: Backend y Lógica:** Completada.
  - Modelos de datos implementados (`Event`, `Activity`, `Student`, `User`, `Attendance`, `Registration`).
  - API RESTful con endpoints CRUD para todas las entidades.
  - Lógica de negocio compleja implementada:
    - Preregistro con validación de cupos (solo para Conferencias, Talleres, Cursos).
    - Control de asistencia para actividades magistrales (check-in, check-out, pausa/reanudar, cálculo automático de porcentaje).
    - Relaciones automáticas entre actividades (asistir a una magistral implica asistencia a otra).
    - Validación de solapamiento de horarios en preregistros.
    - Validación de fechas de actividades dentro del rango del evento.
- **✅ Fase 3: Pruebas:** Completada. Suite de 33 tests unitarios/integración pasando, validando modelos, endpoints, servicios y flujos de negocio.
- **✅ Fase 4: Validación de Flujos:** Completada. Flujos completos de usuario validados manualmente.
- **✅ Fase 5: UI/UX:** Completada.
  - Frontend estructurado con Tailwind CSS y Alpine.js.
  - Dashboard de administrador funcional con stats, navegación persistente y manejo de estado.
  - CRUD de Eventos implementado y funcional.
  - CRUD de Actividades implementado, funcional y con validaciones de negocio.
  - Dashboard de estudiante funcional:
    - Autenticación funcional para estudiantes (validación contra sistema externo).
    - Navegación por pestañas funcional y persistente.
    - Vista de Eventos disponibles con preregistro.
    - Vista detallada de Actividades por Evento con representación tipo cronograma.
    - Representación visual precisa de actividades multídias como bloques diarios con horarios específicos.
    - Diferenciación automática entre eventos de un solo día y multídias.
    - Vista de Mis Preregistros con gestión de preregistros personales.
    - Perfil de estudiante funcional (lectura).
- **🔄 Fase 6: Funcionalidades Avanzadas:** En desarrollo.
  - Generación de constancias.
  - Reportes y estadísticas avanzadas.
  - Finalización e integración completa del frontend (gestión completa de asistencias para estudiantes).

## **4. Estructura del Proyecto (Backend/Frontend)**

```bash
app/
├── __init__.py                # Factoría principal Flask
├── models/                    # Modelos SQLAlchemy
│   ├── activity.py
│   ├── attendance.py
│   ├── event.py
│   ├── registration.py
│   ├── student.py
│   ├── user.py
│   └── __init__.py
├── api/                       # Blueprints REST (endpoints)
│   ├── activities_bp.py
│   ├── attendances_bp.py
│   ├── auth_bp.py
│   ├── registrations_bp.py
│   ├── events_bp.py
│   └── students_bp.py
├── services/                  # Lógica de negocio reutilizable
│   ├── activity_service.py
│   ├── attendance_service.py
│   ├── event_service.py
│   ├── registration_service.py
│   ├── student_service.py
│   ├── user_service.py
│   └── __init__.py
├── schemas/                   # Marshmallow schemas
│   ├── activity_schema.py
│   ├── attendance_schema.py
│   ├── event_schema.py
│   ├── registration_schema.py
│   ├── student_schema.py
│   ├── user_schema.py
│   └── __init__.py
├── templates/                 # Templates Jinja2
│   ├── admin/
│   ├── student/
│   └── base.html
├── static/
│   ├── css/
│   ├── js/
│   │   ├── app.js
│   │   ├── helpers/
│   │   │   └── dateHelpers.js
│   │   ├── admin/
│   │   │   ├── dashboard.js
│   │   │   ├── activities.js
│   │   │   ├── attendances_list.js
│   │   │   └── ...
│   │   └── __tests__/
│   │       ├── app.coverage.test.js
│   │       ├── dateHelpers.unit.test.js
│   │       └── ...
│   └── icons/
├── migrations/                # Alembic (Flask-Migrate)
│   └── ...
├── run.py                     # Entry point para desarrollo
├── requirements.txt           # Dependencias Python
└── README.md                  # Documentación principal
```

## **5. Principales Casos de Uso**

- **Estudiantes:** Preregistro y registro de asistencia a actividades, consulta de eventos disponibles, visualización de cronogramas y gestión de preregistros personales.
- **Administradores:** Creación y edición de eventos y actividades, gestión de usuarios, generación de reportes y constancias, monitoreo de asistencia en tiempo real.
- **Reportes:** Exportación de datos de asistencia, generación de estadísticas por evento, actividad y estudiante.

## **6. Seguridad y Autenticación**

- Autenticación basada en JWT para estudiantes y administradores.
- Validación de roles y permisos en endpoints protegidos.
- Almacenamiento seguro de tokens en `localStorage` y manejo de expiración/corrupción.

## **7. Pruebas y Calidad**

- Cobertura de pruebas backend con Pytest (modelos, servicios, endpoints).
- Pruebas de frontend con Jest/jsdom (módulos JS, integración con API).
- Mocking de servicios externos y utilidades para pruebas reproducibles.
- Validación manual de flujos críticos antes de cada release.

## **8. Despliegue y Entorno**

- Entorno de desarrollo local con SQLite y configuración sencilla vía `.env`.
- Despliegue en producción con MariaDB y configuración de variables de entorno seguras.
- Migraciones gestionadas con Alembic/Flask-Migrate.
- Documentación de comandos útiles para desarrollo y pruebas.

## **9. Roadmap y Mejoras Futuras**

- Finalización de reportes avanzados y constancias automatizadas.
- Integración con sistemas externos de validación de estudiantes.
- Mejoras en la experiencia de usuario y accesibilidad.
- Implementación de notificaciones y recordatorios automáticos.
- Optimización de rendimiento y escalabilidad.
