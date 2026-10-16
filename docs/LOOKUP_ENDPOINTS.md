# Endpoints de lookup (selectores sin `per_page=1000`)

## 1. Motivo

Los selectores y filtros del admin necesitaban **todas** las opciones de una
sola vez, y la forma de conseguirlas era pedir el listado genérico con un
`per_page` enorme:

| Vista                                                               | Llamada anterior                | Coste real                              |
| ------------------------------------------------------------------- | ------------------------------- | --------------------------------------- |
| `registrations` (selector de estudiantes)                           | `/api/students?per_page=1000`   | 2253 objetos **completos**              |
| `reports` (selector de carreras)                                    | `/api/students?per_page=1000`   | 2253 objetos, solo para montar un `Set` |
| `registrations`, `reports`, `students`, `attendances` (actividades) | `/api/activities?per_page=1000` | 111 objetos completos                   |
| `registrations`, `reports`, `attendances` (eventos)                 | `/api/events?per_page=1000`     | 2 objetos                               |
| `calendar`, `dashboard`, `overview`                                 | `/api/events?per_page=100`      | 2 objetos                               |
| `student/event_activities`                                          | `/api/activities?per_page=2000` | todas las de un evento                  |

Un objeto completo de `Activity` arrastra `description`, `requirements`,
`speakers` (JSON), `target_audience` (JSON), `created_at`, `updated_at`… y de
`Student`, además, `email`. Nada de eso consume un `<select>`.

Los endpoints de lookup devuelven **la lista completa pero con un payload
reducido**, y no pagan el peaje de la paginación.

## 2. Endpoints

### `GET /api/students/lookup[?search=]`

> **Requiere token de admin** (ver §4).

```json
{ "students": [ { "id", "control_number", "full_name", "career" } ], "total": 2253 }
```

Solo los cuatro campos del selector. **No** incluye `email` ni fechas.
`search` filtra por número de control o nombre (case-insensitive).

### `GET /api/students/public-lookup?control_number=<n>`

> **Único endpoint de estudiantes SIN autenticación, a propósito.**

```json
{
  "student": {
    "control_number": "26690330",
    "full_name": "Ana López",
    "career": "ISC",
    "email": "..."
  }
}
```

Existe porque la preregistración pública y el registro rápido de staff
necesitaban resolver un número de control a datos básicos, y ese era el
único motivo por el que no se podía proteger `GET /api/students/`
(hallazgo §1.1: ese listado anida `registrations` y `attendances`).

Características que lo hacen seguro para dejarlo abierto:

- **Coincidencia exacta** por número de control: devuelve 0 o 1, así que
  no sirve para enumerar el padrón. Un prefijo (`2669033`) devuelve `404`.
- Solo los cuatro campos que esos flujos leen; nada de `id`, historial ni
  fechas.
- `404` cuando no existe y `400` si falta el parámetro.

Sus dos únicos call sites: `public/registrations_public.js` y
`public/staff_walkin.js`.

### `GET /api/students/careers`

> **Requiere token de admin** (ver §4).

```json
{ "careers": ["Ingeniería Ambiental", "..."], "total": 10 }
```

Carreras distintas ya normalizadas en la base, ordenadas sin distinguir
mayúsculas. Reemplaza el `Set` que `reports.js` montaba en el navegador.
Excluye `NULL` y vacíos.

### `GET /api/activities/lookup[?event_id=&activity_type=&department=&search=]`

```json
{ "activities": [ { "id", "name", "code", "event_id", "department",
                    "activity_type", "start_datetime", "end_datetime",
                    "event": { "id", "name" } } ], "total": 111 }
```

`event` viene **anidado** porque `registrations.html` muestra
`` `${activity.name} (${activity.event?.name})` `` junto a cada opción.
Se resuelve con `joinedload`, sin N+1.

### `GET /api/events/lookup[?status=active&search=&sort=start_date:desc]`

```json
{ "events": [ { ...Event.to_dict(), "public_url": "..." } ], "total": 2 }
```

Devuelve el dict completo del evento (son 2), porque `dashboard` y
`overview` necesitan `start_date`, `end_date` e `is_active` para filtrar y
formatear. `sort` se valida contra una whitelist de columnas.

### `GET /api/activities/by-event/<int:event_id>[?for_student=&exclude_types=&activity_type=&sort=&search=]`

```json
{ "activities": [ { ...Activity.to_dict(), "event": { "id", "name" },
                    "current_capacity": 12, "current_registrations": 12 } ],
  "total": 66,
  "event": { "id": 1, "name": "45 Aniversario Tec Valles" } }
```

**No pagina**: devuelve todas las actividades de **un** evento. Existe porque
la vista del portal del estudiante agrupa por día y necesita el conjunto
completo, con los campos ricos (`duration_hours`, `max_capacity`,
`current_capacity`). Un lookup reducido no serviría, y el tope de
`max_per_page=100` del listado genérico habría truncado la respuesta en
silencio.

- `for_student=true` excluye las de tipo `Magistral` (misma regla que el
  listado genérico).
- `current_capacity` cuenta los preregistros **vigentes** (excluye
  `Ausente` y `Cancelado`) en una sola consulta.
- Devuelve `404` si el evento no existe.

## 3. `max_per_page=100` en los listados genéricos

Con los selectores migrados, los listados pueden acotarse sin romper nada:

| Endpoint                    | Aplicado en                                |
| --------------------------- | ------------------------------------------ |
| `/api/students/`            | `paginate(..., max_per_page=100)`          |
| `/api/activities/`          | `paginate(..., max_per_page=100)`          |
| `/api/events/`              | `paginate(..., max_per_page=100)`          |
| `/api/registrations/`       | `paginate(..., max_per_page=100)`          |
| `/api/attendances/`         | clamp manual (pagina con `limit`/`offset`) |
| `/api/public/registrations` | clamp manual                               |

Cualquier `per_page` mayor que 100 queda en 100.

## 4. Nota sobre autenticación

No hay protección JWT global en la app (no existe `before_request`), así
que cada endpoint se defiende solo. La regla quedó así:

| Endpoint                                                           | Token                                            | Por qué                                                                                                                                                                                                                                                                                                                                              |
| ------------------------------------------------------------------ | ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `students/` (listado), `students/lookup`, `students/careers`       | **admin** (`@jwt_required()` + `@require_admin`) | Son datos personales del padrón. El listado además anidaba `registrations` y `attendances`: sin token, enumerar por nombre o número de control bastaba para reconstruir el historial académico de cualquiera (hallazgo §1.1). Se exige admin y no solo `@jwt_required()` porque un estudiante autenticado también podría descargar el padrón entero. |
| `students/public-lookup`                                           | **ninguno, a propósito**                         | Ver §2. Es el sustituto público del listado para la preregistración y el walk-in de staff.                                                                                                                                                                                                                                                           |
| `students/<id>/hours-by-event`, `students/<id>/event/<id>/details` | **cualquiera + propiedad**                       | Antes no llevaban token: con el mío se leían las horas de otra persona (B-1). Ahora el estudiante solo accede a las suyas; el admin, a las que quiera.                                                                                                                                                                                               |
| `activities/lookup`, `events/lookup`, `activities/by-event/<id>`   | **ninguno**                                      | No contienen datos personales (nombre, horario, tipo y aforo de la actividad) y esa misma información se publica en las páginas de preregistración abiertas. Si algún día se protegen, hacerlo con `@jwt_required()` basta: los únicos consumidores son el panel del admin y el portal del estudiante, ambos con token.                              |

## 5. Pruebas

`tests/api/test_lookup_endpoints.py` cubre el contrato de los endpoints de
esta guía, los filtros, el `404`, la exclusión de `Magistral`, el conteo de
`current_capacity` (incluida la exclusión de `Ausente`/`Cancelado`) y el
tope de `max_per_page=100`. Como los dos lookups de estudiantes ya exigen
token, esos tests autentican con `auth_headers`.

`tests/api/test_students_api_security.py` cubre lo que §4 describe: que el
listado y los lookups de estudiantes responden `401` sin token y `403` con
token de estudiante, que `public-lookup` devuelve solo los cuatro campos y
no admite enumeración por prefijo, y la propiedad de los datos en
`hours-by-event`, `event/<id>/details` y el listado de preregistros.

```bash
python -m pytest -q tests/api/test_lookup_endpoints.py tests/api/test_students_api_security.py
```
