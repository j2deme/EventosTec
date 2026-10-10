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

```json
{ "students": [ { "id", "control_number", "full_name", "career" } ], "total": 2253 }
```

Solo los cuatro campos del selector. **No** incluye `email` ni fechas.
`search` filtra por número de control o nombre (case-insensitive).

### `GET /api/students/careers`

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

Estos endpoints **no** llevan `@jwt_required()`, igual que los listados
genéricos de los que derivan (`/api/students/`, `/api/activities/`,
`/api/events/` tampoco lo llevan; no hay protección JWT global en la app).
El payload de `students/lookup` es más pequeño que el del listado, pero
expone los mismos campos que ya estaban accesibles sin autenticación.

Si algún día se protegen los listados, hay que proteger los lookup a la vez.

## 5. Pruebas

`tests/api/test_lookup_endpoints.py` cubre el contrato de los cinco
endpoints, los filtros, el `404`, la exclusión de `Magistral`, el conteo de
`current_capacity` (incluida la exclusión de `Ausente`/`Cancelado`) y el
tope de `max_per_page=100`.

```bash
python -m pytest -q tests/api/test_lookup_endpoints.py
```
