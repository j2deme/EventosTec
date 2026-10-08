# Registro rápido de staff (walk-in)

Vista móvil **pública** para que el personal de un evento registre la
asistencia de un estudiante que no aparece, en segundos y sin login.

| Ruta                                           | Autenticación     | Archivo                                                       |
| ---------------------------------------------- | ----------------- | ------------------------------------------------------------- |
| `GET /public/staff-walkin/<activity_ref>`      | Ninguna (pública) | `app/api/public_registrations_bp.py:public_staff_walkin_view` |
| `GET /public/staff-walkin?slug=<activity_ref>` | Ninguna (pública) | ídem (`public_staff_walkin_query`)                            |

`activity_ref` acepta `public_slug` (preferido) o ID numérico. Solo se sirve
para actividades `activity_type == "Magistral"`; el enlace lo genera el panel
admin en _Actividades → ver → enlaces públicos_ (`tokenUrlStaffWalkin`).

Archivos de la vista:

- Plantilla: `app/templates/public/staff_walkin.html`
- Lógica: `app/static/js/public/staff_walkin.js` (factory `staffWalkin()` que
  Alpine monta con `x-data`; se carga **sin** `defer` para que exista antes que
  Alpine, que sí va con `defer` en el `<head>`)
- Tests: `app/static/js/public/__tests__/staff_walkin.test.js` (Jest),
  `tests/test_templates_x_cloak.py` (render) y
  `tests/api/test_public_confirm_slug.py` (endpoint de confirmación)

## Flujo de búsqueda (`lookup()`)

Se dispara al escribir (debounce 300 ms) y con Enter; requiere ≥ 8 caracteres.

1. **Base local** `GET /api/students/?search=<num>&per_page=10` → coincidencia
   **exacta** de `control_number`. Si hay match, **no** se consulta nada más
   de identidad.
2. Solo sin match local: `GET /api/students/validate?control_number=<num>`
   (proxy del servicio externo, timeout 8 s).
   - 404 → `state = 'not_found'`
   - 503/502/red → `state = 'lookup_error'` (**no** es "no encontrado": el
     alumno puede estar en la base local) y se ofrece reintentar.
3. `GET /api/public/registrations?activity_id=<ref>&q=<num>&per_page=20` →
   decide la acción ofrecida, **solo con coincidencia exacta** de control:

| Fila encontrada               | Acción (`actionMode`)  |
| ----------------------------- | ---------------------- |
| `registration` sin `attended` | `confirm_reg`          |
| `registration` con `attended` | `cancel_reg` (Ausente) |
| `attendance` con `attended`   | `cancel_attendance`    |
| ninguna                       | `create` (walk-in)     |

> `q` filtra por **subcadena** (control _o_ nombre) en el backend; por eso no
> se usa `regs[0]` como fallback: podía apuntar al registro de otro alumno.

Acciones (todas requieren la ventana abierta y usan `activity_id` = slug):

| Acción              | Endpoint                                                      |
| ------------------- | ------------------------------------------------------------- |
| `create`            | `POST /api/public/registrations/walkin`                       |
| `confirm_reg`       | `POST /api/public/registrations/<id>/confirm`                 |
| `cancel_reg`        | `POST /api/public/registrations/<id>/confirm` (`mark_absent`) |
| `cancel_attendance` | `POST /api/public/attendances/<id>/toggle`                    |

`POST .../confirm` acepta **slug o numérico** en `activity_id`
(`resolve_activity_by_id`); hasta 2026-10 hacía `int(activity_id)` y con un
slug respondía 500, dejando sin efecto _Confirmar asistencia_ y _Marcar
Ausente_ (`tests/api/test_public_confirm_slug.py`).

## Ventana de staff

- **Frontend**: abierta mientras `now <= activity_start + 25 min`. Se
  re-evalúa al buscar, antes de cada acción y cada 30 s (así una pestaña
  abierta se cierra sola sin recargar). Fecha desconocida → abierta.
- **Backend**: **no** valida esos 25 min; solo la ventana global de
  confirmación (`end_datetime + public_confirm_window_days`). La regla de los
  25 min es, por tanto, una restricción de UI. _Pendiente de decidir si se
  traslada al servidor._

## Anti-FOUC (red lenta)

- `base.html` sirve `app/static/css/tailwind.css` **precompilado y local**
  (bloqueante): el primer pintado ya sale con estilos y la fuente global
  vive en el preflight + CSS propio. Antes cargaba `cdn.tailwindcss.com`
  (~400 KB de JS que compilaban utilidades en el navegador): con `defer`
  dejaba la página sin estilos y sin él se quedaba en blanco en red lenta.
  Ver `docs/STATIC_ASSETS.md` (cómo regenerar vendor/tailwind.css).
- La plantilla **ya no lleva su CSS crítico**: con Tailwind local era
  redundante (duplicaba el preflight). `{% block head %}` sigue existiendo en
  `base.html` por si alguna plantilla necesita CSS propio.
- `x-cloak` en todos los `x-show` (el estado `idle` queda sin cloakear a
  propósito, como guía inicial); el `<h1>` lleva el nombre renderizado por
  servidor para no salir en blanco.

## Límites conocidos

- **Sin autenticación**: cualquiera con el enlace registra asistencias (ver
  `docs/STUDENT_MODULE_REVIEW.md`, hallazgo D-1). No se tocó a propósito.
- La ventana de 25 min no se valida en el servidor (arriba).
- El límite es solo superior: no impide registrar antes del inicio de la
  actividad.
