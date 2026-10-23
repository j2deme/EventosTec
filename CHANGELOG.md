# Changelog

Todo cambio notable de la plataforma queda registrado aquí.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/),
y este proyecto se adhiere a [Semantic Versioning](https://semver.org/lang/es/).
Las etiquetas siguen el patrón `vX.Y.Z` a partir de `v1.0.0`; la etiqueta
anterior, `v0.9` (2025-12-05), conserva su formato original porque ya estaba
publicada.

## [Unreleased]

### Añadido

- **`deploy.sh` tolerante a la red y con diagnóstico pronto.** El punto de
  decisión se desplaza al segundo 10, nunca a la hora:
  - **Preflight de ~10 s** antes del `git pull`: daemon de Docker,
    DNS/conectividad de los 6 hosts que el build necesita (GitHub, Debian,
    NodeSource, PyPI, pythonhosted, npm) y aviso si el checkout tiene < 3 GB.
  - **Compuerta de velocidad**: mide el throughput real contra
    `deb.debian.org`; por debajo de 500 KB/s aborta con la medición y una
    estimación del tiempo de build (se fuerza con `DEPLOY_ALLOW_SLOW_NET=1`).
    El build de 38,9 min del 2026-10-22 habría sido cortado en ~10 s.
  - **Tope duro de 15 min** por intento (`DEPLOY_BUILD_TIMEOUT`, `0` lo
    desactiva): acota la única modalidad en la que nada falla —red viva pero
    a gotas—. No se reintenta solo: reporta la capa actual y decides tú.
  - **Reintentos solo para errores de red rápida** (hasta 3, backoff 15/30 s,
    evaluados sobre el log **del intento actual**); un error determinista
    aborta al primer intento.
  - **`trap` con clasificación de causa** (RED / DISCO / DOCKER /
    DESCONOCIDO), aviso de si producción sigue con la imagen anterior y
    últimas 15 líneas del log.
  - **Log persistente** por ejecución en `deploy-logs/` (gitignored).
  - Baseline medido: build sano ≈ 6 min (red buena) vs 38,9 min (90 KB/s).

## [1.0.0] — 2026-10-22

Primera versión estable y etiquetada. Cierra el ciclo `v0.9` → `1.0.0`
(2026-09-25 → 2026-10-22, ~110 commits): los módulos de créditos
complementarios, el auto-registro y la asistencia llegan a madurez, y los
hallazgos que bloqueaban la etiqueta quedan resueltos y cubiertos por pruebas.

### Seguridad

Los cuatro hallazgos que bloqueaban la etiqueta, todos verificados en vivo
contra el contenedor y con pruebas que **fallan** contra el código anterior:

- **`GET /api/students/` ya no es anónimo.** Devolvía el padrón completo con
  `registrations` y `attendances` anidados: enumerando por nombre o número de
  control se reconstruía el historial académico de cualquiera (a qué actividad
  se preregistró cada quién y con qué horario de entrada/salida). Ahora
  exige token de administrador, no solo autenticación —un estudiante
  autenticado también habría podido descargar el padrón entero—.
- **Nuevo `GET /api/students/public-lookup?control_number=`.** Fue lo que hizo
  posible proteger el listado sin romper la preregistración pública ni el
  registro rápido de staff, que solo necesitaban resolver un número de control
  a datos básicos. Coincidencia **exacta** (0 o 1 resultado: ya no se puede
  enumerar por prefijo) y solo `{control_number, full_name, career, email}`.
- **Horas y detalle por evento son propios** (`hours-by-event`,
  `event/<id>/details`): antes aceptaban cualquier token. El chequeo de
  propiedad va antes del `404` para no servir de oráculo de existencia de ids.
- **IDOR en el listado de preregistros**: con token de estudiante se ignoraba
  el parámetro `student_id` ajeno. El `POST` ya bloqueaba preregistrar a
  terceros.
- **XSS almacenado en el modal multídías**: el nombre de la actividad (lo
  escribe el administrador) se inyectaba con `insertAdjacentHTML` sin escapar.
  Un nombre como `<img src=x onerror=...>` se ejecutaba en el navegador del
  estudiante. Ahora todo lo interpolado pasa por `escapeHtml`.
- Se liberaba el handler de teclado al cerrar el modal (antes quedaba vivo y
  pisaba cualquier otro manejo global), y un doble clic ya no deja dos modales
  con el mismo `id`.
- Revocación real del token en el servidor al cerrar sesión; claim `type` en
  el JWT que desambigua administrador y estudiante (colisionan espacio de ids);
  rate-limit y validación en proceso del auto-registro; las listas públicas
  solo aceptan `public_slug`, nunca el id numérico.

### Añadido

- **Créditos complementarios (Fase 3)**: acumulación multi-evento
  (`event_ids`), exclusión derivada de los ya acreditados, overrides manuales
  (`credit_overrides`), tabla `credit_grants` para el otorgamiento, export con
  una columna por evento y UI con desglose y badges. Todo apoya en un servicio
  unificado de horas que comparten créditos y reportes (fuente única).
- **Auto-registro público**: confirmación tras registrarse, verificación al
  cerrar la sesión, ventana de apertura configurable desde ajustes, QR
  imprimible del enlace y renombrado a «Auto-registro».
- **Asistencia**: tolerancia de llegada y llegada real dentro del porcentaje
  de asistencia, cierre real en lote (`batch checkout`) con descuento de la
  pausa abierta, lista pública imprimible con export XLSX, lista imprimible
  para instructores y la asistencia ya visible en «Mis registros» del
  estudiante.
- **Importación masiva** de actividades desde plantilla XLSX con la estructura
  documentada; la importación almacena hora local (sin desfase de huso).
- **Vista de calendario** por evento en el administrador, con sesiones
  expandidas, indicador «Sesión n/m» y ficha completa; índice de días sticky
  en la vista del estudiante.
- **`activityTypeHelpers`** como fuente única de presentación por tipo de
  actividad (paleta, iconos y duración por sesión): la lista del admin, el
  calendario, la vista pública y la del estudiante cambian a la vez.
- Cambio y recuperación de contraseña del administrador (apuntando al MAB).
- Sincronización con el servicio externo (`sync-external`) en sustitución de
  la búsqueda e importación externa de estudiantes.
- Logout real con revocación del token; Google Sans como fuente global.

### Cambiado

- **Paginación en toda la plataforma.** La ventana de páginas se calcula con
  `paginationHelpers.buildState()` y el markup vive en un único partial
  (`partials/pagination.html`) usado por las 9 vistas. Con 2 252 estudiantes
  la vista anterior renderizaba un botón por página (226) y la pantalla crecía
  hacia la derecha. Ahora la ventana está acotada, hay salto directo a página,
  selector de filas y ninguna vista envuelve el include con su propia guarda.
- **`max_per_page=100`** en los listados genéricos y cinco endpoints de
  _lookup_ (`students/lookup`, `students/careers`, `activities/lookup`,
  `events/lookup`, `activities/by-event/<id>`) que devuelven la lista completa
  pero con el payload que consume un `<select>`: los selectores ya no descargan
  `per_page=1000` con objetos completos.
- Asistencias pagina a 50 por página (6 098 filas → 122 páginas; antes eran
  610), Prerregistros a 50 y Estudiantes a 25.
- Orden cronológico por fecha de inicio en el portal del estudiante.
- Retirada la impersonación de la tabla de Prerregistros (el modal y el
  endpoint siguen disponibles donde aportan).

### Corregido

- **Huso horario**: asistencias, check-in, pausa, check-out, fechas de
  preregistro y confirmación, la Fecha Registro del listado, los XLSX de
  créditos, el semestre de la matriz de reportes y la importación masiva
  persisten y se muestran en hora local (Fase 1 de fechas y toda la ronda de
  correcciones posterior). Formato canónico es-MX de 24 h sin AM/PM.
- Los archivos descargados estampan la hora local en su nombre.
- La búsqueda con filtros en Prerregistros ya no devuelve 500.
- El cierre de asistencia recalcula bien y sincroniza el preregistro.
- «Próximos Eventos» conserva los eventos ya iniciados y pagina bien.
- Confirmación de asistencia cuando el identificador es el `public_slug`.
- Corregida la vista de staff-walkin (lookup, ventana de atención y aviso de
  éxito) y su parpadeo antes de cargar los assets.
- Iconos Tabler inexistentes y 4 clases Tailwind inválidas (`border-1`,
  `ml-13`, `text-md`, `preline`).
- El botón «Editar evento» del overview abre el editor correcto.
- **El panel ya no lanza 12 `TypeError` en cada carga.** `calendar.html`
  evaluaba `calendar.event.name`, `calendar.days.length`, etc. con `calendar`
  aún en `null`: `x-show` solo oculta el nodo, no impide que Alpine evalue la
  expresión, así que el error aparecía en la consola en cada F5 sin romper la
  interfaz. Ahora todas esas expresiones (resumen, `x-show` y los dos `x-for`
  del índice de días) usan `?.`, y el `x-text` de `selectedActivity.duration_hours`
  —cuyo `x-show` lo protegía solo a él— también.
- **Sin scroll horizontal de página a 1280 px** en Estudiantes y
  Prerregistros. Las tablas nunca desbordaban su contenedor `overflow-x-auto`:
  el culpable era `<main class="flex-1">` sin `min-w-0`, cuyo `min-width:auto`
  de hijo flex impedía que se encojiera, con lo que crecía hasta el ancho de la
  tabla y el desborde ocurría en el documento (89 px y 191 px). Con `min-w-0`
  el desborde baja a 0 px y el scroll ocurre dentro de la tabla, como está
  diseñado; a 1440/1920 px ya funcionaba. No se añadió ninguna clase
  `overflow-*`, que romperían el índice de días `sticky` del calendario.
- El contenedor Docker apuntaba a la base local por un `.env` obsoleto.
- `deploy.sh` aborta en el primer error y muestra el `HEAD` desplegado.
- **Un corte de red ya no puede dejar el build colgado ~34 minutos.** El paso
  de NodeSource hacía `curl … | bash -` sin límite de tiempo: con el DNS caído
  la petición esperó 2030 s hasta rendirse (`Could not resolve host`). Ahora
  `curl` baja el script a un fichero con `--connect-timeout 10 --max-time 60`
  (que cubre también la resolución DNS, lo que `--connect-timeout` no siempre
  hace) y `--retry 2 --retry-max-time 120`: el peor caso queda en ≤ ~2 min y
  el fallo típico sale en segundos (6 s con NXDOMAIN, 36 s con TCP colgado,
  medido). De paso, la descarga a fichero sustituye a la tubería `| bash`:
  en `sh` sin `pipefail`, un `curl` fallido habría devuelto 0 y el error real
  habría salido después, desplazado y engañoso, en el `apt-get` siguiente.
  Los dos `apt-get` pasan a `Acquire::Retries=3` (por defecto, 0). pip y npm
  ya traían sus propios límites (15 s/5 reintentos y 5 min/2 reintentos).

### Rendimiento

- **Fin del N+1 en los listados del admin**: los cuatro listados más pesados
  precargaban de golpe lo que serializaban fila a fila. Medido contra la BD
  de producción, por página de 25–50 filas:

  | Vista            | Antes                  | Después             |
  | ---------------- | ---------------------- | ------------------- |
  | Estudiantes      | 99 consultas · 11,5 s  | 7 consultas · 1,1 s |
  | Asistencias      | 113 consultas · 13,4 s | 9 consultas · 2,1 s |
  | Prerregistros    | 71 consultas · 8,2 s   | 8 consultas · 1,3 s |
  | Lista imprimible | 39 consultas · 5,2 s   | 6 consultas · 0,8 s |

  Con `selectinload` en las colecciones y `joinedload` solo en `many-to-one`
  (para no tocar el `COUNT` del paginado). En Asistencias las
  preregistraciones de la página pasan a resolverse en una sola consulta en
  vez de una por fila. `tests/api/test_query_budget.py` fija un presupuesto
  de consultas por petición para que no regrese: hoy 5/5 fallan contra el
  código anterior.

- **Sin CDNs**: Tailwind precompilado y los assets de terceros versionados y
  servidos desde el propio contenedor. Se acabó el FOUC (pantalla en blanco
  hasta que llegaban los CDNs) y la dependencia de red en el arranque.
- Pestañas del dashboard con inicialización perezosa; se eliminaron endpoints
  sin uso en asistencias, actividades, eventos, reportes y registros públicos.
- Logging del contenedor acotado en tamaño y cantidad.

### Documentación

- `AGENTS.md` como guía para agentes que trabajen en el repo, con los
  contratos JSON que no deben romperse.
- Guía de assets estáticos (`docs/STATIC_ASSETS.md`), de los endpoints de
  lookup (`docs/LOOKUP_ENDPOINTS.md`), del auto-registro
  (`docs/SELF_REGISTER.md`) y de la vista de staff-walkin.
- Registros de despliegue y del estado de las correcciones de huso horario.

### Limitaciones conocidas

Alcance honesto de 1.0.0 — nada de esto bloquea la etiqueta, pero está
declarado para no llevarlo por sorpresa a 1.1:

- **Módulo del estudiante sin modernizar**: sigue en Alpine.js 2 con un JS por
  pestaña (~3 400 líneas en 7 archivos). Solo 3 archivos tienen pruebas, y
  ninguna cubre navegación, registro ni cancelación.
- **`docs/SELF_CHECKOUT_PLAN.md`**: el plan de auto-checkout del estudiante
  queda para 1.1+.
- **Deuda de mantenibilidad del módulo del estudiante**: `redirectToLogin`
  duplicado en 7 archivos, `getCurrentStudentId` con 4 semánticas distintas,
  formateadores de fecha/hora duplicados pese a existir `dateHelpers.js`, y
  modales sin `role="dialog"` ni foco inicial (accesibilidad).
- **`GET /api/activities/`, `/api/events/` y los lookups de actividades y
  eventos siguen sin token**: no contienen datos personales y esa misma
  información se publica en las páginas de preregistro abiertas. La regla
  completa está en `docs/LOOKUP_ENDPOINTS.md` §4.
- Inconsistencias menores heredadas: `canRegisterForActivity` y
  `availabilityCode` no coinciden cuando falta `max_capacity`, y algunas
  rutas declaradas con barra final se llaman sin ella (un `308` por
  petición).

## [0.9] — 2025-12-05

Última etiqueta antes del ciclo 1.0. Detalles anteriores a esta fecha no se
han reconstruido aquí a propósito: no existe un registro fiable de esos
cambios y preferimos no inventarlo.

[unreleased]: https://github.com/j2deme/EventosTec/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/j2deme/EventosTec/compare/v0.9...v1.0.0
[0.9]: https://github.com/j2deme/EventosTec/releases/tag/v0.9
