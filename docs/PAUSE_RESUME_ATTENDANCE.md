# Pausa y Reactivación de Asistencia

## Descripción

Esta funcionalidad permite pausar y reanudar asistencias para actividades de tipo "Magistral". Es útil para controlar casos donde los estudiantes llegan a una conferencia, se registran para obtener el punto por asistencia y posteriormente se retiran.

**Restricción temporal:** La vista pública de pausa/reactivación solo está disponible desde 30 segundos después del inicio de la actividad hasta 1 minuto después de su finalización.

## Componentes Implementados

### 1. Backend (API)

#### Admin Endpoints (requieren autenticación JWT + rol Admin)
- `POST /api/attendances/pause` - Pausa una asistencia
- `POST /api/attendances/resume` - Reanuda una asistencia pausada

#### Public Endpoints (usan token público de actividad)
- `GET /public/pause-attendance/<token>` - Vista pública mobile-first para control de asistencia
- `GET /api/public/attendances/search` - Busca asistencias por nombre o número de control
- `POST /api/public/attendances/<attendance_id>/pause` - Pausa una asistencia (público)
- `POST /api/public/attendances/<attendance_id>/resume` - Reanuda una asistencia (público)

**Nota:** Todos los endpoints públicos incluyen validación temporal que solo permite acceso durante el período de la actividad (30 segundos después del inicio hasta 1 minuto después del fin).

### 2. Frontend

#### Vista de Administrador
- Botones de pausa/reactivación en la lista de asistencias (`/admin/attendances`)
- Los botones solo aparecen para actividades de tipo "Magistral"
- Se muestra el botón de pausa cuando la asistencia está activa (check-in sin check-out)
- Se muestra el botón de reanudar cuando la asistencia está pausada
- Usa iconos de Tabler Icons (web font)

#### Vista Pública
- Vista mobile-first accesible mediante token público
- Buscador de estudiantes por nombre o número de control
- Botones grandes optimizados para dispositivos móviles
- Mínimos clics requeridos para pausar/reanudar
- Usa iconos de Tabler Icons (web font) en lugar de SVGs
- **Restricción temporal:** Solo disponible durante el período de la actividad (30s después del inicio hasta 1 min después del fin)

## Uso

### Desde la Vista de Administrador

1. Ir a "Gestión de Asistencias"
2. Filtrar por actividad de tipo "Magistral"
3. Ubicar al estudiante en la lista
4. Hacer clic en el botón de pausa (⏸) o reanudar (▶) según corresponda

### Desde la Vista Pública

1. Obtener el token público de la actividad Magistral
   - El token se genera automáticamente para cada actividad
   - Formato: `/public/pause-attendance/<token>`
2. Abrir la URL en un dispositivo móvil o desktop
   - **Importante:** La vista solo estará disponible 30 segundos después del inicio de la actividad
   - La vista dejará de estar disponible 1 minuto después de finalizada la actividad
3. Buscar al estudiante por nombre o número de control
4. Hacer clic en "Pausar" o "Reanudar" según corresponda

## Características

- **Solo para actividades Magistral**: La funcionalidad solo está disponible para conferencias magistrales
- **Restricción temporal**: Vista pública disponible solo durante el período de la actividad (30s después inicio - 1min después fin)
- **Validaciones de estado**: 
  - Solo se puede pausar si hay check-in registrado
  - No se puede pausar si ya hay check-out
  - Solo se puede reanudar si la asistencia está pausada
- **Cálculo automático**: El sistema calcula automáticamente la duración neta descontando los tiempos de pausa
- **Mobile-first**: La vista pública está optimizada para uso en dispositivos móviles
- **Iconos web font**: Utiliza Tabler Icons mediante web font para mejor rendimiento

## Ejemplo de Flujo

1. Estudiante llega a la conferencia magistral (después de 30s del inicio)
2. Se registra su check-in (asistencia activa)
3. Estudiante sale temporalmente
4. Staff pausa su asistencia desde la vista pública
5. Estudiante regresa
6. Staff reanuda su asistencia
7. Al finalizar, se hace check-out
8. El porcentaje de asistencia se calcula descontando el tiempo pausado

## Notas Técnicas

- Los campos `is_paused`, `pause_time` y `resume_time` se almacenan en la tabla `attendances`
- El servicio `calculate_attendance_percentage` considera automáticamente las pausas
- Los endpoints públicos validan el token y verifican que la actividad sea de tipo Magistral
- La búsqueda en la vista pública solo muestra asistencias con check-in registrado
- La validación temporal se aplica en todos los endpoints públicos (vista, búsqueda, pause, resume)
- Mensajes de error descriptivos cuando se intenta acceder fuera del período permitido
- Los iconos utilizan la biblioteca Tabler Icons mediante web font (más eficiente que SVGs inline)
