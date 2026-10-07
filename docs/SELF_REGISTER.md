# Auto-registro (self check-in)

Flujo público para que un asistente **que no se preregistró** se marque a la
llegada, sin intervención del personal. Es el QR que se genera desde el
detalle de la actividad.

## 1. Ventana de registro (configurable)

El formulario solo acepta check-in dentro de un rango alrededor del **inicio**
de la actividad:

```
abre   = inicio - public_self_register_open_minutes_before_start   (default 30)
cierra = inicio + public_self_register_close_minutes_after_start   (default 20)
```

- **Fuente única**: `app/services/self_register_service.py`
  (`self_register_state()`), usada tanto por la vista `GET` (habilita/oculta
  el form y pasa el deadline al countdown) como por el `POST` (acepta o
  rechaza). Antes el límite superior estaba hardcodeado en tres lugares
  (GET, JS y POST) y **no existía límite inferior**: un QR generado días
  antes permitía check-in anticipado.
- Estados: `open` / `not_open` / `closed`. `not_open` y `closed` devuelven
  mensajes distintos (`window_message()`), que se exponen al frontend en
  `data-activity-message` y se muestran en el panel de "no disponible".
- El countdown del cliente usa **solo** `data-activity-deadline` (deadline
  calculado por el backend); se eliminó el fallback `start + 20 min` del JS.
  El deadline solo se pasa con la ventana **abierta**, para que el modo
  verificación no oculte el formulario al expirar.
- **Verificar después del cierre**: con `closed` el formulario se muestra en
  _modo verificación_ (`verify_only`, banner amarillo) en lugar de ocultarse,
  para que quien ya se registró pueda confirmarlo. En el `POST`, `not_open`
  se rechaza **antes** de llamar al sistema externo (barato) y `closed` se
  evalúa **después** de validar credenciales, de modo que el duplicado
  responde `409 already_registered` con su asistencia en vez de "la ventana
  terminó".

Configuración (ENV o `scripts/initialize_app_settings.py`):

| Key                                              | Default | ENV                                                  |
| ------------------------------------------------ | ------- | ---------------------------------------------------- |
| `public_self_register_open_minutes_before_start` | 30      | `APP_PUBLIC_SELF_REGISTER_OPEN_MINUTES_BEFORE_START` |
| `public_self_register_close_minutes_after_start` | 20      | `APP_PUBLIC_SELF_REGISTER_CLOSE_MINUTES_AFTER_START` |

> Para editarlas desde la UI de Settings hay que sembrarlas:
> `python scripts/initialize_app_settings.py`.

### Ejemplo: adelantar la apertura de una actividad

Si una actividad necesita abrir más pronto de lo que dice el default (p. ej.
una conferencia de las **13:00** que debe abrir a las **11:50**), sube el
minuto de apertura a `70`:

- **UI**: `Admin → Settings` →
  `public_self_register_open_minutes_before_start = 70`. Aplica en ~10 s (TTL
  de caché), sin reiniciar.
- **ENV**: `APP_PUBLIC_SELF_REGISTER_OPEN_MINUTES_BEFORE_START=70` en `.env`.
  Fija el valor (queda bloqueado en la UI) y requiere reiniciar el contenedor.

No hay que tocar código ni migrar. Dos notas:

- El valor es **global**: todas las actividades abrirían 70 min antes de su
  inicio. Eso no altera el porcentaje de asistencia, porque la presencia se
  recorta a la ventana real de la actividad (`calculate_attendance_percentage`).
- El cierre sigue siendo `inicio + public_self_register_close_minutes_after_start`
  (default 20). Conviene regresar el default a 30 al terminar el evento.

## 2. Rate limit

`POST /api/registrations/self` y `POST /api/auth/student-login` comparten el
mismo contador de intentos (`SlidingWindowLimiter`, en memoria por proceso):

| Clave                                      | Intentos | Ventana |
| ------------------------------------------ | -------- | ------- |
| por número de control                      | 8        | 300 s   |
| por IP (`X-Forwarded-For` o `remote_addr`) | 80       | 300 s   |

Respuesta: `429` con `RATE_LIMIT_MESSAGE`. El límite se aplica **antes** de
llamar al sistema externo. Constantes en
`app/services/student_auth_service.py::CREDENTIAL_ATTEMPT_LIMITS`;
`reset_credential_limits()` las limpia (tests).

**Intentos que no consumen cuota**: cuando el request ya pasó la validación
de credenciales y aun así se rechaza por una razón que no es de
autenticación, se devuelve el intento del número de control con
`refund_credential_attempt()`:

- duplicado → `409 already_registered` (el estudiante ansioso que reintenta
  no debe agotar la cuota de 8 y terminar en un confuso 429);
- ventana cerrada sin registro previo → `400` con `window_message()`.

El contador **por IP** nunca se devuelve: sigue siendo la red de seguridad
contra el abuso desde una misma IP. `SlidingWindowLimiter.refund()` es la
primitiva (tests en `tests/services/test_rate_limit.py`).

## 3. Validación de credenciales en proceso (sin loopback HTTP)

Antes el `POST /api/registrations/self` hacía una llamada HTTP al
**propio** `/api/auth/student-login` (`request.host_url + ...`): dependía de
que la app alcanzara su URL pública (proxy/DNS/TLS) y costaba una llamada de
red por check-in.

Ahora ambos endpoints llaman a `student_auth_service.validate_student_credentials()`
(misma función, mismo budget de rate-limit):

| Excepción                      | `POST /api/auth/student-login` | `POST /api/registrations/self` |
| ------------------------------ | ------------------------------ | ------------------------------ |
| `CredentialsRateLimited`       | 429                            | 429                            |
| `InvalidCredentials`           | 401 `Credenciales inválidas`   | 401                            |
| `CredentialServiceUnavailable` | 503                            | 503 (mensaje propio)           |

`upsert_student()` centraliza la creación/actualización del `Student` local
(incluye carrera) en ambos flujos. Ya no se devuelve `error: str(e)` al
cliente: los detalles se registran con `current_app.logger`.

## 4. Política de estado y horas

El self check-in **abre la sesión**; el resultado se decide en el cierre
(checkout individual o `batch-checkout`), que es el comportamiento pedido
para conferencias:

1. **Check-in** → `Attendance.status = "Parcial"`, sesión abierta. La
   `Registration` **no** se cambia a `Asistió` (antes sí, en el momento de la
   llegada); solo se marca `attended = True` para que la lista pública muestre
   "Confirmado" en vez de "No asistió" mientras la sesión está abierta.
2. **Cierre** → `calculate_attendance_percentage()` calcula
   `>= 80% → Asistió`, `> 0% → Parcial`, `0% → Ausente` y
   `sync_registration_status()` propaga el resultado a la preregistración:
   - `>= 80%` → `Registration.status = "Asistió"` (+ horas),
   - `< 80%` → `Registration.status = "Ausente"` (**no acredita**; esto es lo
     único que quita las horas que `hours_service` da por `Confirmado`),
   - sesión abierta → no se toca nada.

   Aplica a `POST /api/attendances/register` (edición con check-out) y a
   `POST /api/attendances/batch-checkout`. `dry_run` incluye en `details`
   el campo `registration_status` (preview).

3. **Pausas** (ver `docs/PAUSE_RESUME_ATTENDANCE.md`):
   - una pausa abierta al cierre **sí descuenta** hasta el `check_out`
     (antes `batch-checkout` la auto-reanudaba con duración 0 y el alumno que
     se fue y no volvió acreditaba);
   - cada ciclo pausa/reanuda se pliega en `check_in_time` (la tabla solo
     guarda un intervalo), así que salir varias veces sí descuenta;
   - la pausa está habilitada para `Magistral` **y** `Conferencia`
     (`attendance_service.has_session_control`).

### Qué ve el estudiante en cada fase

| Fase                               | QR `/public/self-register/<slug>`                                       | Portal "Mis registros"                                        |
| ---------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------- |
| Antes de abrir                     | "El auto-registro aún no abre…" (form oculto)                           | `Registrado` / `Confirmado`                                   |
| Ventana abierta, sin registrar     | Formulario                                                              | `Registrado` / `Confirmado`                                   |
| Check-in hecho (sesión `Parcial`)  | Tarjeta ✅ "¡Asistencia registrada!" con "Entrada: HH:MM" y "Continuar" | Badge **Asistencia registrada** + nota con la hora y el aviso |
| Reintento (`409`)                  | La misma tarjeta ✅ (no un error)                                       | igual                                                         |
| Ventana cerrada, **ya** registrado | Formulario en modo verificación (banner) → `409` con la misma tarjeta   | Badge **Asistencia registrada**                               |
| Ventana cerrada, no registrado     | `400` con `window_message()`                                            | `Registrado` / `Confirmado`                                   |
| Checkout del admin (`>= 80%`)      | —                                                                       | `Asistió` (política de §4)                                    |

- El badge y la nota del portal salen de
  `app/static/js/helpers/registrationStatus.js` (`visibleStatus()` /
  `note()`), la única fuente para ese texto. Usan el campo `attendance` que
  `GET /api/registrations` agrega a cada item con **una sola query batch**;
  sin ese campo el helper cae al flag `attended` del schema.

## 5. Endpoints

| Método | Ruta                               | Notas                                                                                                                     |
| ------ | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| GET    | `/public/self-register/<slug\|id>` | vista pública (slug primero)                                                                                              |
| GET    | `/self-register`                   | legacy; acepta `?activity=<id>`                                                                                           |
| POST   | `/api/registrations/self`          | `201` ok, `400` campos/ventana, `401` credenciales, `404` actividad, `409` duplicado, `429` límite, `503` sistema externo |

Payload: `{"control_number", "password", "activity_id"}` (`activity_id`
acepta el slug público).

Respuestas de éxito y de duplicado:

- `201` → `{"message", "attendance"}`: sesión recién abierta.
- `409` → `{"code": "already_registered", "message", "attendance"}`: la
  asistencia ya existente. La UI pinta **la misma pantalla de confirmación**
  que el 201 (tarjeta ✅ con "Entrada: HH:MM" y botón "Continuar") en vez de
  un error, y el endpoint devuelve el intento de rate-limit (ver §2).

## 6. Pruebas

- `tests/api/test_self_register_api.py` — contrato del `POST` (ventana,
  credenciales, duplicado, rate-limit, sin loopback, `Registration` intacta).
- `tests/services/test_self_register_service.py` — cálculo de la ventana.
- `tests/services/test_student_auth_service.py` — mapeo de errores y límites.
- `tests/test_public_slug_views.py` — vistas `GET`.
- `app/static/js/public/__tests__/self_register.test.js` — countdown y
  mensajes del frontend.
- `tests/test_datetime_utils_wall_local.py` — convención de escritura
  (sección 7).

## 7. Convención horaria de los tiempos de asistencia

Las columnas `datetime` de MySQL guardan **hora local naive** (la misma
convención que `activities.start_datetime` y los payloads del cliente). Los
instantes que genera el servidor se persisten con `db_wall_local()` /
`db_now_local()` (`app/utils/datetime_utils.py`):

- `self_register_bp` escribe el `check_in_time` del auto check-in con
  `db_wall_local(now)`; igual `attendances_bp`, `registrations_bp`,
  `public_registrations_bp` y `attendance_service` (`pause_time`).
- Guardar `datetime.now(timezone.utc)` (o `db.func.now()`, con el servidor
  MySQL en UTC) dejaba la hora UTC en la columna: al leerla como local, el
  check-in quedaba +6 h respecto a la actividad, la ventana de presencia
  salía invertida y el porcentaje salía 0 %. Detalle, evidencia y tabla de
  sitios convertidos en `docs/TIMEZONE_FIX.md`.
- Los valores que vienen del payload **no** se convierten:
  `parse_datetime_with_timezone()` conserva el wall time del cliente.
