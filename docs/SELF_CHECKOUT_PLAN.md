# Plan: Self-checkout público + desfase de conferencias

> **Estado: BORRADOR PARA REVISIÓN — nada de este plan está implementado.**
> Fecha: 2026-10-08 · Solo se registró este documento; no se ejecutó ningún
> paso del plan ni se tocaron archivos de código.
> Relacionado: `docs/SELF_REGISTER.md` (auto-registro actual),
> `docs/ATTENDANCE_PERCENTAGE.md`, `docs/STATIC_ASSETS.md`.

---

## 0. Decisiones ya tomadas (revisión de esta versión)

| #   | Decisión                                                                   |
| --- | -------------------------------------------------------------------------- |
| 1   | Construir **ahora**, con `public_self_checkout_enabled = 0` (flag apagado) |
| 2   | Desfase de eventos en vivo → **`shift_minutes` en el batch-checkout**      |
| 3   | Tarjeta de salida: **solo la hora** (sin % provisional)                    |
| 4   | Alcance: **solo Magistral/Conferencia** (control de sesión)                |

---

## 1. Principio rector (la garantía anti-regresión)

**Un solo escritor del estado final.** El self-checkout **solo escribe
`check_out_time`**. El estado de la preregistración (`Asistió` / `Ausente`),
las horas acreditadas y las asistencias relacionadas siguen siendo
**exclusivos del batch-checkout del admin**, que es quien cierra en el momento
real del evento.

Consecuencias:

- Un evento desfasado **nunca** condena a un estudiante desde su teléfono: la
  decisión de acreditación ocurre cuando el staff cierra con el horario ya
  corregido (o con `shift_minutes`).
- No hay lógica duplicada batch vs self (misma semántica, distinto momento) →
  se elimina la principal fuente de divergencias.
- Escape hatch ya existente: el admin puede editar la salida de una asistencia
  con `POST /api/attendances/register` (`check_out_time`).

---

## 2. El problema del desfase (verificado en el código)

La ventana del porcentaje **no usa `end_datetime`**: usa
`start_datetime + duration_hours` (`attendance_service.py::_activity_window_utc`,
línea 75) y recorta la presencia por **intersección**
(`compute_attendance_metrics`).

Ejemplo del evento real (charla de las 13:00):

| Situación                                                                                                              | Cálculo                                            | Resultado        |
| ---------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ---------------- |
| Programado 13:00–14:00 (`duration_hours = 1`), corre **13:20–14:20**, estudiante presente 13:15–14:20 (toda la charla) | `[13:15,14:20] ∩ [13:00,14:00]` = 45/60 min = 75 % | **`Ausente`** ❌ |
| Igual, pero el admin corrigió el horario (start 13:20, duración 1 h) antes de cerrar                                   | `[13:15,14:20] ∩ [13:20,14:20]` = 60/60 = 100 %    | `Asistió` ✅     |

Dos matices importantes descubiertos al verificar:

1. **`duration_hours` es un campo manual en el editor**
   (`admin/partials/activities.html:1480`, `x-model="currentActivity.duration_hours"`).
   `calculatedDuration` (`activities.js:342`) es solo informativo en la UI: si
   el staff cambia la hora de fin y olvida la duración, el % se sigue
   calculando contra la ventana vieja → **modo fallo humano** del protocolo
   manual. El `shift_minutes` (§4) existe justamente para no depender de eso.
2. **`duration_hours` también alimenta las horas acreditadas**
   (`hours_service.py:90,107`): corregir el horario cambia las horas
   acreditadas (normalmente deseable: refleja la duración real). El
   `shift_minutes` **no** toca nada de eso (solo el cálculo del cierre).

Hoy ese caso "se salva" porque el batch-checkout pone
`check_out = hora del cierre` e ignora la salida real. Por eso el orden
importa: **registrar salidas reales (self-checkout) sin finalizar el estado**
hace el dato más fiel sin arriesgar créditos; el cierre decide.

---

## 3. Alcance A — Self-checkout (misma vista/QR, adaptada por hora) · flag OFF

### 3.1 Settings nuevos

Seed con `scripts/initialize_app_settings.py` (idempotente: solo crea si no
existe). Editables en **Admin → Settings**; aplican en ~10 s
(`SettingsManager` TTL de caché = 10 s; ENV tiene prioridad y bloquea la key).

| Key                                             | Tipo | Default | Descripción                                                     |
| ----------------------------------------------- | ---- | ------- | --------------------------------------------------------------- |
| `public_self_checkout_enabled`                  | bool | **0**   | Kill switch global: apagado ⇒ comportamiento idéntico al actual |
| `public_self_checkout_open_minutes_after_start` | int  | 20      | Abre al mismo tiempo que cierra el check-in (transición limpia) |
| `public_self_checkout_close_minutes_after_end`  | int  | **120** | Holgura para conferencias que terminan desfasadas               |

- - getters estáticos en `AppSettings` (`app/services/settings_manager.py`).
- Nota: `SettingsManager.get(key, default)` funciona sin fila en la BD (usa el
  default), pero **para que la key aparezca en la UI hay que correr el seed**
  tras el deploy.

### 3.2 Servicio (`app/services/self_register_service.py`)

- `self_checkout_window(activity) -> (opens_at, closes_at) | None`
- `self_checkout_state(activity) -> (OPEN | NOT_OPEN | CLOSED, opens_at, closes_at)`
- Gate: `attendance_service.has_session_control(activity)` → **solo
  Magistral/Conferencia** (para el resto, `state` siempre `CLOSED`/no
  disponible y la vista no cambia).
- Constantes nuevas junto a `OPEN/NOT_OPEN/CLOSED` ya existentes.

### 3.3 Vista GET (`app/api/self_register_bp.py::self_register_form`)

Máquina de modos con prioridades deterministas (evita solapes):

| Condición                                                              | `mode`                  |
| ---------------------------------------------------------------------- | ----------------------- |
| Ventana de entrada abierta (`self_register_state == OPEN`)             | `checkin`               |
| Entrada cerrada + flag on + sesión control + ventana de salida abierta | `checkout`              |
| Cualquier otro caso                                                    | `verify` (tal cual hoy) |

- Flag **off** o actividad sin control de sesión ⇒ respuesta **idéntica a la
  actual** (cero cambio visible mañana).
- El `countdown` solo aplica en `checkin` (como hoy).

### 3.4 POST `/api/registrations/self` con `action`

`action: "checkin" | "checkout"`; **ausente ⇒ `checkin`** (backward
compatible: los clientes viejos no cambian).

Orden de validaciones en `checkout` (espejo del check-in):

1. Flag/ventana de salida → `400` con `window_message()` (antes del servicio
   externo).
2. Credenciales → mismo rate-limit (`8/300` por control, IP sin reembolso) y
   mismo reembollo en respuestas `409`.
3. Sesión abierta: `check_in` sin `check_out` para (estudiante, actividad).

Escritura (todo lo que **no** se toca es la regla de oro):

| Se escribe                                                                         | No se toca                                                                                                                                                            |
| ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `check_out_time = db_wall_local(now)` (hora local naive, convención ya verificada) | `attendance_percentage`, `Attendance.status`, `Registration` (`status`/`attended`), asistencias relacionadas, `is_paused`/`pause_time` (la cierra el batch, como hoy) |

Respuestas:

| Código | Payload                                                                        | UI                                      |
| ------ | ------------------------------------------------------------------------------ | --------------------------------------- |
| `201`  | `{action:"checkout", message, attendance}`                                     | Card **"Salida registrada: HH:MM"**     |
| `409`  | `{code:"already_checked_out", ...}` + reembollo                                | La misma card con la hora ya registrada |
| `409`  | sin sesión abierta → mensaje "No tienes entrada registrada, acércate al staff" | card de error amable                    |
| `400`  | flag off / ventana cerrada / tipo no permitido                                 | `window_message()`                      |
| `429`  | límite de intentos                                                             | igual que hoy                           |

### 3.5 Frontend público

- `app/static/js/public/self_register.js`: lee `mode` del init, define la
  acción que envía, variantes de título/botón
  ("Registrar entrada" / "Registrar salida") y la card de salida **solo con
  la hora**.
- `app/templates/public/self_register.html`: cabecera/banner por modo; la
  tarjeta compartida 201/409 existente **no se toca**.
- Un **mismo QR/URL** sirve para todo el ciclo (entrada → salida →
  verificación).

### 3.6 Portal del estudiante

- La nota de "asistencia registrada" pasa a mostrar
  **"Entrada: HH:MM · Salida: HH:MM"** cuando `attendance.check_out_time`
  exista (el `attendance_schema` ya lo expone y el endpoint ya inyecta
  `attendance`; solo frontend: `helpers/registrationStatus.js` +
  `student/partials/registrations.html`).

---

## 4. Alcance B — `shift_minutes` en batch-checkout (desfase)

- **Contrato**: `POST /api/attendances/batch-checkout`
  `{activity_id, dry_run, shift_minutes?}` · entero, rango propuesto
  `-60..+360` · default `0` ⇒ comportamiento **idéntico** al actual.
- **Cálculo**: `compute_attendance_metrics(..., window_shift_minutes=0)`
  desplaza `act_start`/`act_end` (obtenidos de `_activity_window_utc`) **solo
  en memoria**; `calculate_attendance_percentage(attendance_id,
window_shift_minutes=0)` lo pasa. Sin escritura en `activities` (no toca
  calendario, horas acreditadas ni ventanas de registro).
- **Efecto cascada deseado**: `%`, `sync_registration_status` (≥80 →
  `Asistió`, <80 → `Ausente`) y `create_related_attendances` usan el mismo
  cálculo corrido.
- **UI**: campo numérico "El evento se desfasó (min)" en el modal de
  batch-checkout (`admin/partials/attendances.html:53` +
  `admin/attendances.js:518`), visible en el paso de **dry_run** para
  previsualizar con y sin desfase antes de cerrar.
- **Protocolo operativo de un evento desfasado**:
  1. El self-checkout sigue abierto (ventana con holgura de §3.1).
  2. Al terminar: `dry_run=1` + `shift_minutes=+N` → revisar `details` por fila.
  3. Repetir sin `dry_run` para cerrar.
  - Alternativa manual (sin código): editar horario real **y
    `duration_hours`** en el editor y cerrar sin `shift_minutes`
    (riesgo: olvidar la duración, §2.1).

---

## 5. Alcance C — Tests, docs, commits y rollout

### 5.1 Tests

**pytest** (nuevo `tests/api/test_self_checkout_api.py`):

- flag **off** ⇒ mismas respuestas que hoy (regresión pura);
- ventana `NOT_OPEN`/`CLOSED` → `400` con mensaje;
- actividad sin control de sesión → no disponible;
- sin sesión abierta → `409`/mensaje, **sin crear asistencia**;
- happy path → `201`, `check_out_time` en hora local (`created_at −
check_out ≈ 0` como señal de verificación), **`status` y
  `attendance_percentage` intactos**;
- duplicado → `409` + reembollo de cuota;
- con `is_paused` → se escribe la salida y `is_paused` queda como estaba;
- modo `verify` del check-in sin cambios.

**pytest** para `shift_minutes` (unidad + endpoint):

- charla 13:00–14:00 con presencia completa y salida 14:20 → 75 % con `0` y
  100 % con `+20`;
- endpoint sin `shift_minutes` ⇒ byte a byte igual al comportamiento actual;
- dry_run no persiste nada.

**Jest**:

- `public/__tests__/self_register.test.js`: modo, `action` enviada, card de
  salida, fallbacks;
- input de desfase en `admin/__tests__/attendances*.test.js`;
- nota "Entrada · Salida" en `student/__tests__/registrationStatus.test.js`.

### 5.2 Docs

- `docs/SELF_REGISTER.md`: § "Self-checkout" (ventana, modo, respuestas) +
  § "Desfase de eventos" con el protocolo de `shift_minutes`.
- `AGENTS.md`: contratos (`POST /api/registrations/self` con `action`;
  `batch-checkout` con `shift_minutes`).

### 5.3 Commits (3, atómicos)

1. `feat(self-checkout): salida desde la vista pública (flag off)` —
   settings + servicio + endpoint + vista + tests + docs.
2. `feat(student): muestra la salida junto a la entrada en "Mis registros"`.
3. `feat(attendances): shift_minutes en batch-checkout para eventos desfasados`.

### 5.4 Validación (obligatoria antes de cada commit)

```bash
npm ci && npm run build:static        # ver docs/STATIC_ASSETS.md (§9)
./venv/Scripts/python.exe -m pytest -q
npx jest --runInBand
./venv/Scripts/python.exe -m ruff check --ignore E902 --ignore F401 app tests
npx prettier --check <archivos tocados>
./venv/Scripts/pre-commit.exe run --files <archivos>   # + commit --no-verify (CRLF/WSL)
```

### 5.5 Rollout y rollback

1. Deploy (`docker compose build web && docker compose up -d web`).
2. Seed de settings → verificar las 3 keys en Admin → Settings.
3. **Flag off**: mañana el comportamiento es el actual (cubierto por tests de
   regresión).
4. Habilitar ~30 min antes de un evento de prueba; observar logs.
5. Cierre con `dry_run` + `shift_minutes` si hubo desfase.
6. **Rollback inmediato**: apagar el flag en Admin → Settings (~10 s, sin
   deploy); si algo del endpoint falla, `action` por defecto sigue siendo
   `checkin`.

---

## 6. Riesgos y mitigaciones

| Riesgo                                           | Mitigación                                                                                                              |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| Regresión en el check-in (víspera de evento)     | Flag off = respuestas idénticas; tests de regresión; nada del flujo actual cambia                                       |
| Evento termina fuera de la hora programada       | Ventana de salida con holgura (120 min) + `shift_minutes` con previsualización                                          |
| Refresh/doble escaneo de salida                  | `409` idempotente con la misma card + reembollo de cuota                                                                |
| Estudiante se va antes del 80 % y "pierde" horas | El self-checkout **no finaliza**; el admin decide al cerrar y puede editar la salida                                    |
| Abuso / intentos masivos                         | Rate-limit actual (control/IP) + flag como kill switch                                                                  |
| Hora desfasada en la columna                     | `db_wall_local(now)` (convención ya verificada, ver `docs/TIMEZONE_FIX.md`)                                             |
| Staff olvida cerrar la actividad                 | Mismo riesgo que hoy (el self-checkout no lo empeora); mejora opcional: aviso de actividades con sesiones abiertas (§7) |
| Pausa abierta al hacer checkout                  | Se conserva `is_paused`; el batch la cierra y descuenta como hoy (test explícito)                                       |

---

## 7. Fuera de alcance (futuras mejoras)

- **% en la tarjeta de salida** — descartado por ahora (puede salir engañoso
  con desfases).
- **Capa automática de desfase** (inferir el corrimiento de los check-ins
  reales) — descartada: difícil de explicar y riesgosa.
- **Checkout con token de sesión** emitido en el check-in (evitar la segunda
  validación de credenciales) — menos llamadas externas pero añade estado
  nuevo; se evalúa después.
- **Recordatorio "actividades sin cerrar"** en el dashboard de admin.
- **Migración del QR vendorizado** a la convención de assets (§9).

---

## 8. Puntos a verificar durante la implementación

1. ¿`SettingsManager.set_in_db` crea la fila si la key no existe? (si sí, la
   UI permite crear keys sin seed; si no, el seed es obligatorio).
2. Interacción pausa + checkout (test con `is_paused=True` y `pause_time`
   dentro/fuera de la ventana).
3. Solape de ventanas si el admin configura
   `open_minutes_after_start` > `close_minutes_after_start` (definir
   prioridad: `checkin` gana mientras la entrada esté abierta).
4. Coste de la validación de credenciales: 1 llamada externa extra por
   estudiante (entrada + salida) — razonable para 200+ personas, pero
   confirmar límites del proveedor.
5. Semántica de `409` de salida vs `409` de entrada en el mismo payload
   (`code` diferenciados: `already_registered` / `already_checked_out`).

---

## 9. Nota: convención de assets estáticos (nueva desde `docs/STATIC_ASSETS.md`)

El repo pasó a **sin CDNs**: `npm ci && npm run build:static` genera
`app/static/vendor/` y `app/static/css/tailwind.css` (no versionados); los
Docker/CI lo ejecutan y en local hay que correrlo **antes** de servidor o
pytest (`tests/test_static_assets.py` lo exige).

Dos consecuencias para este plan:

1. Los cambios de frontend de este plan son JS propio (`self_register.js`,
   `registrationStatus.js`) y plantillas: si se añade una **clase Tailwind
   nueva o un icono `ti ti-*` nuevo**, hay que regenerar
   (`npm run build:static`) o los tests 3/4 fallan.
2. **Deuda abierta**: el QR del auto-registro quedó vendorizado a mano en
   `app/static/js/vendor/qrcode.min.js` (referenciado en
   `admin/base.html:409`), pero la regla 3 de `docs/STATIC_ASSETS.md` dice
   que un asset de terceros se añade en `package.json` (pineado) +
   `scripts/vendor_static.mjs` + `base.html`. Los tests pasan (el fichero es
   local y versionado), pero convendría migrarlo en un commit aparte
   (`chore(assets): mueve qrcodejs al build vendor`), lo que implica también
   actualizar `docs/SELF_REGISTER.md` §8.

---

## 10. Esfuerzo estimado

| Bloque                                                   | Estimado    |
| -------------------------------------------------------- | ----------- |
| A: settings + servicio + endpoint + vista + tests + docs | ~4–5 h      |
| A: frontend público + portal                             | ~1.5 h      |
| B: `shift_minutes` (service + endpoint + modal + tests)  | ~2–3 h      |
| Validación completa + 3 commits                          | ~1 h        |
| **Total**                                                | **~9–11 h** |
| Opcional: migración del QR a la convención de assets     | +0.5 h      |

---

### Archivos previstos (mapa rápido)

| Archivo                                                                                             | Cambio                                       |
| --------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| `app/services/settings_manager.py`                                                                  | getters de los 3 settings                    |
| `scripts/initialize_app_settings.py`                                                                | seed de las 3 keys                           |
| `app/services/self_register_service.py`                                                             | ventana/estado de salida + modo              |
| `app/api/self_register_bp.py`                                                                       | `mode` en GET, `action` en POST              |
| `app/static/js/public/self_register.js`                                                             | UI por modo, card de salida                  |
| `app/templates/public/self_register.html`                                                           | cabecera/banner por modo                     |
| `app/services/attendance_service.py`                                                                | `window_shift_minutes` en metrics/percentage |
| `app/api/attendances_bp.py`                                                                         | `shift_minutes` en batch-checkout            |
| `app/templates/admin/partials/attendances.html`                                                     | input de desfase                             |
| `app/static/js/admin/attendances.js`                                                                | enviar `shift_minutes`                       |
| `app/static/js/helpers/registrationStatus.js`                                                       | nota "Entrada · Salida"                      |
| `app/templates/student/partials/registrations.html`                                                 | idem                                         |
| `docs/SELF_REGISTER.md`, `AGENTS.md`                                                                | contratos y protocolo                        |
| `tests/api/test_self_checkout_api.py` (nuevo), `tests/api/test_registrations*.py`, tests de metrics | cobertura                                    |
