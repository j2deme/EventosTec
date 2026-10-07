# Pausa y Reactivación de Asistencia

## Descripción

Esta funcionalidad permite pausar y reanudar asistencias en actividades con **control de sesión** (tipo "Magistral" y "Conferencia"). Es útil para controlar casos donde los estudiantes llegan a una conferencia, se registran (presencial o con self check-in) y temporalmente se retiran: una salida corta con retorno no debe afectar su asistencia, pero quien se retira y no regresa no debe acreditar.

**Restricción temporal:** La vista pública de pausa/reactivación solo está disponible dentro de la ventana configurada en `public_pause_available_from_seconds` (desde el inicio) y `public_pause_available_until_after_end_minutes` (hasta después de la finalización).

## Componentes Implementados

### 1. Backend (API)

#### Admin Endpoints (requieren autenticación JWT + rol Admin)

- `POST /api/attendances/pause` - Pausa una asistencia
- `POST /api/attendances/resume` - Reanuda una asistencia pausada
- `POST /api/attendances/batch-checkout` - Cierra todas las sesiones abiertas al final de la actividad
- `POST /api/attendances/register` - Check-in/check-out individual (la modal de edición)

#### Public Endpoints (usan el `public_slug` o el id de la actividad)

- `GET /public/pause-attendance/<ref>` - Vista pública mobile-first para control de asistencia
- `GET /api/public/attendances/search` - Busca asistencias por nombre o número de control
- `POST /api/public/attendances/<attendance_id>/pause` - Pausa una asistencia (público)
- `POST /api/public/attendances/<attendance_id>/resume` - Reanuda una asistencia (público)

**Nota:** Todos los endpoints públicos incluyen validación temporal que solo permite acceso durante la ventana configurada.

### 2. Frontend

#### Vista de Administrador

- Botones de pausa/reactivación en la lista de asistencias (`/admin/attendances`)
- Los botones aparecen para actividades con control de sesión (Magistral y Conferencia)
- Se muestra el botón de pausa cuando la asistencia está activa (check-in sin check-out)
- Se muestra el botón de reanudar cuando la asistencia está pausada
- Usa iconos de Tabler Icons (web font)

#### Vista Pública

- Vista mobile-first accesible mediante el enlace público de la actividad
- Buscador de estudiantes por nombre o número de control
- Botones grandes optimizados para dispositivos móviles
- Mínimos clics requeridos para pausar/reanudar
- Usa iconos de Tabler Icons (web font) en lugar de SVGs
- **Restricción temporal:** Solo disponible dentro de la ventana configurada

## Uso

### Desde la Vista de Administrador

1. Ir a "Gestión de Asistencias"
2. Filtrar por actividad con control de sesión (Magistral o Conferencia)
3. Ubicar al estudiante en la lista
4. Hacer clic en el botón de pausa (⏸) o reanudar (▶) según corresponda
5. Al finalizar la actividad, ejecutar el **batch checkout** para cerrar todas las sesiones

### Desde la Vista Pública

1. Obtener el enlace público de la actividad
   - Se genera en el detalle de la actividad
   - Formato: `/public/pause-attendance/<public_slug>`
2. Abrir la URL en un dispositivo móvil o desktop
   - **Importante:** Solo estará disponible dentro de la ventana de control
3. Buscar al estudiante por nombre o número de control
4. Hacer clic en "Pausar" o "Reanudar" según corresponda

## Características

- **Magistral y Conferencia**: el criterio vive en `attendance_service.has_session_control` (lo comparten la UI del admin, la vista pública y el check-in automático)
- **Restricción temporal**: ventana configurable vía `AppSettings`
- **Validaciones de estado**:
  - Solo se puede pausar si hay check-in registrado
  - No se puede pausar si ya hay check-out
  - Solo se puede reanudar si la asistencia está pausada
- **Cálculo automático**: el porcentaje descuenta el tiempo pausado (>= 80% → `Asistió`, > 0% → `Parcial`, 0% → `Ausente`)
- **Múltiples pausas**: cada ciclo pausa/reanuda se **pliega en `check_in_time`** al reanudar, porque la tabla solo guarda un intervalo de pausa (`pause_time`/`resume_time`). Así salir varias veces sí descuenta; `created_at` conserva la hora real de llegada al evento
- **Pausa abierta al cierre**: si la asistencia queda pausada al hacer el check-out (batch-checkout o edición individual), el tiempo pausado **sí se descuenta** hasta el check-out: el alumno que se fue y no volvió queda bajo el umbral
- **Mobile-first**: La vista pública está optimizada para uso en dispositivos móviles
- **Iconos web font**: Utiliza Tabler Icons mediante web font para mejor rendimiento

## Ejemplo de Flujo

1. Estudiante llega a la conferencia y hace self check-in (o es registrado por el staff): queda en `Parcial` con la sesión abierta
2. Estudiante sale temporalmente (café/agua)
3. Staff pausa su asistencia desde la vista pública o el admin
4. Estudiante regresa
5. Staff reanuda su asistencia (el tiempo pausado queda descontado)
6. Al finalizar, se ejecuta el **batch checkout** (o el check-out individual de quien se retiró)
7. El porcentaje se calcula descontando el tiempo pausado
8. La preregistración cierra con el resultado: `>= 80%` → `Asistió` (acredita), `< 80%` → `Ausente` (no acredita)

## Notas Técnicas

- Los campos `is_paused`, `pause_time` y `resume_time` se almacenan en la tabla `attendances`
- `resume_attendance` pliega la pausa transcurrida en `check_in_time` y limpia `pause_time`/`resume_time` para el siguiente ciclo
- `calculate_attendance_percentage` (y su versión pura `compute_attendance_metrics`, que usa el dry-run del batch-checkout) considera automáticamente las pausas
- `sync_registration_status` propaga el resultado del checkout a la preregistración
- Los endpoints públicos validan la ventana temporal y que la actividad tenga control de sesión (Magistral/Conferencia)
- La búsqueda en la vista pública solo muestra asistencias con check-in registrado
- Mensajes de error descriptivos cuando se intenta acceder fuera del período permitido
- Los iconos utilizan la biblioteca Tabler Icons mediante web font (más eficiente que SVGs inline)
