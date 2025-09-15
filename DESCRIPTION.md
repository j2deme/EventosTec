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
- **🔄 Fase 5: UI/UX:** En desarrollo avanzado.
  - Frontend estructurado con Tailwind CSS y Alpine.js.
  - **Dashboard de administrador funcional** con stats, navegación persistente y manejo de estado.
  - **CRUD de Eventos implementado y funcional.**
  - **CRUD de Actividades implementado, funcional y con validaciones de negocio.**
  - **Dashboard de estudiante funcional:**
    - **Autenticación funcional** para estudiantes (validación contra sistema externo).
    - **Navegación por pestañas** funcional y persistente.
    - **Vista de Eventos disponibles** con preregistro.
    - **Vista detallada de Actividades por Evento** con representación tipo cronograma.
    - **Representación visual precisa de actividades multídias** como bloques diarios con horarios específicos.
    - **Diferenciación automática entre eventos de un solo día y multídias.**
    - **Vista de Mis Preregistros** con gestión de preregistros personales.
    - **Perfil de estudiante** funcional (lectura).
- **⏸️ Fase 6: Funcionalidades Avanzadas:** Pendientes.
  - Generación de constancias.
  - Reportes y estadísticas avanzadas.
  - Finalización e integración completa del frontend (gestión completa de asistencias para estudiantes).

## **4. Estructura del Proyecto (Backend/Frontend)**

```bash
app/
├── init.py # Factoría de la aplicación Flask
├── models/ # Modelos de SQLAlchemy
│ ├── activity.py
│ ├── attendance.py
│ ├── event.py
│ ├── registration.py
│ ├── student.py
│ ├── user.py
│ └── init.py
├── api/ # Blueprints de Flask (endpoints)
│ ├── activities_bp.py
│ ├── attendances_bp.py
│ ├── auth_bp.py
│ ├── events_bp.py
│ ├── registrations_bp.py
│ ├── students_bp.py
│ └── init.py
├── schemas/ # Esquemas de Marshmallow
│ ├── activity_schema.py
│ ├── attendance_schema.py
│ ├── event_schema.py
│ ├── registration_schema.py
│ ├── student_schema.py
│ ├── user_schema.py
│ └── init.py
├── services/ # Lógica de negocio
│ ├── activity_service.py # Validación de fechas de actividades
│ ├── attendance_service.py
│ ├── registration_service.py
│ └── init.py
├── utils/ # Utilidades (auth helpers, etc.)
│ ├── auth_helpers.py
│ └── init.py
├── static/ # Archivos estáticos (CSS, JS, imágenes)
│ └── js/
│ ├── app.js # Lógica JavaScript compartida (autenticación, notificaciones)
│ ├── admin/
│ │ ├── dashboard.js # Lógica específica del dashboard admin
│ │ ├── events.js # Lógica para el CRUD de eventos
│ │ └── activities.js # Lógica para el CRUD de actividades
│ └── student/
│ ├── dashboard.js # Lógica base del dashboard estudiante
│ ├── events.js # Lógica para explorar eventos y preregistrarse
│ ├── event_activities.js # Lógica para vista detallada de actividades de un evento
│ ├── registrations.js # Lógica para gestión de preregistros personales
│ └── profile.js # Lógica para perfil del estudiante
└── templates/ # Plantillas HTML (Jinja2)
├── base.html
├── auth/
│ └── login.html
├── admin/
│ ├── base.html
│ ├── dashboard.html
│ └── partials/
│ ├── header.html
│ ├── sidebar.html
│ ├── overview.html
│ ├── events.html
│ ├── activities.html
│ └── reports.html
├── student/
│ ├── base.html
│ ├── dashboard.html
│ └── partials/
│ ├── overview.html
│ ├── events.html # Vista de lista de eventos
│ ├── event_activities.html # Vista detallada de actividades de un evento
│ ├── registrations.html # Vista de preregistros del estudiante
│ └── profile.html # Vista de perfil del estudiante
└── ...
tests/ # Suite de pruebas Pytest
├── conftest.py # Configuración de fixtures
├── test_auth.py
├── test_events.py
├── test_activities.py
├── test_attendances.py
├── test_registrations.py
├── test_activity_validation.py # Tests para validación de fechas
├── test_attendance_service.py
├── test_registration_service.py
├── test_integration_flows.py
└── ...
```

## **5. Funcionalidades Clave Implementadas**

- **Autenticación:** Login separado para estudiantes (validación contra API externa) y administradores (usuarios locales). Protección de endpoints con JWT.
- **Gestión de Eventos/Actividades:** CRUD completo para eventos y actividades. Actividades pueden ser de tipo Magistral, Conferencia, Taller, Curso, Otro. Incluyen relaciones.
- **Preregistro:** Estudiantes pueden preregistrarse a actividades. El sistema valida cupos y solapamiento de horarios.
- **Control de Asistencia:**
  - **Magistrales:** Check-in, pausa, reanudar, check-out. Cálculo automático de porcentaje de asistencia.
  - **Otras:** Registro post-evento de asistencia confirmada.
- **Relaciones Automáticas:** Asistir a una actividad magistral puede generar automáticamente asistencia a otra relacionada.
- **Validaciones:** Cupos, horarios, tipos de actividad, **fechas de actividades dentro del rango del evento**.
- **Dashboard Administrativo:** Interfaz de usuario funcional con:
  - Navegación persistente (manteniendo estado al recargar).
  - Actualización automática de estadísticas.
  - CRUD de Eventos completamente funcional.
  - CRUD de Actividades completamente funcional.
- **Dashboard Estudiantil (Funcional):**
  - **Autenticación y navegación por pestañas.**
  - **Exploración de eventos disponibles.**
  - **Vista detallada de actividades con representación tipo cronograma.**
  - **Representación visual precisa de actividades multídias** como bloques diarios con horarios específicos.
  - **Diferenciación automática entre eventos de un solo día y multídias.**
  - **Gestión de preregistros personales.**
  - **Perfil de estudiante (lectura).**

## **6. Mejoras Visuales Implementadas para Actividades Multídias**

- **Representación Visual Precisa de Actividades Multídias:**
  - Una actividad del `2025-10-08 10:00` al `2025-10-10 17:00` se muestra como **tres bloques separados**:
    - `08/10: 10:00-17:00`
    - `09/10: 10:00-17:00`
    - `10/10: 10:00-17:00`
- **Indicadores Visuales Claros:**
  - Cada bloque muestra claramente "Día X / Y" para indicar en qué día de la serie se encuentra.
  - Los bloques se ordenan cronológicamente por fecha y hora.
- **Preregistro Consistente:**
  - Si una actividad multídias está preregistrada, **aparece marcada en todos los días** donde se muestra su bloque correspondiente.
  - El estado de preregistro se mantiene consistente en todos los bloques.
- **Diseño Responsivo:**
  - La vista de cards en grid se adapta automáticamente a diferentes tamaños de pantalla.
  - En móviles: 1 columna
  - En tablets: 2 columnas
  - En escritorio: 3-4 columnas
- **Ordenamiento Correcto:**
  - Los preregistros se ordenan por fecha y hora de inicio dentro de cada bloque diario.
  - Los bloques diarios se ordenan cronológicamente.

## **7. Problemas/Pendientes Conocidos**

- Funcionalidades como generación de constancias y reportes avanzados aún no están implementadas.
- Funcionalidades como la conexión con la API externa para validación de estudiantes están simuladas en algunos entornos.
- Funcionalidades como el registro de asistencias para actividades magistrales aún no están implementadas en el frontend estudiantil.
- Funcionalidades como el registro de asistencias para actividades no magistrales aún no están implementadas en el frontend estudiantil.
- El frontend para algunas secciones del estudiante (como perfil avanzado) puede requerir más desarrollo.
