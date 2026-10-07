# Lista de asistencia imprimible (admin + vista pública de Jefes)

Dos rutas renderizan **la misma** lista de preregistrados de una actividad,
lista para imprimir:

| Ruta                                                | Autenticación     | Uso                                                            |
| --------------------------------------------------- | ----------------- | -------------------------------------------------------------- |
| `GET /api/reports/attendance_list?activity_id=<id>` | JWT + rol Admin   | Panel admin → Reportes → "4. Lista de asistencia (imprimible)" |
| `GET /public/attendance-list/<public_slug>`         | Ninguna (pública) | Vista de Jefes de Carrera → botón **Imprimir**                 |

`activity_ref` **solo acepta `public_slug`**: a diferencia del resto de vistas
públicas **no** hay fallback a ID numérico, porque el ID se enumera
trivialmente y esta vista imprime nombre + número de control de todos los
preregistrados. Una actividad sin `public_slug` no es imprimible por esta ruta
(el botón **Imprimir** avisa en pantalla y no abre nada).

## Fuente única de verdad

Ambas rutas construyen el contexto con
`app.services.attendance_list_service.build_attendance_list_context(activity)`:

```python
{
  "event": Event | None,
  "activity": Activity,
  "students": [ {id, full_name, control_number, career}, ... ],  # orden: full_name
  "dates": [date | None, ...],      # una entrada por día (multiday) o [día]
  "multi_day": bool,                # → columnas por día en vez de "Asistencia"
}
```

La plantilla compartida es `app/templates/admin/reports/attendance_list.html`
(tiene botón **Imprimir** con `window.print()` y **Regresar**, ambos ocultos con
`print:hidden`).

## Frontend (vista de Jefes)

`app/static/js/public/event_registrations_public.js`:

- `printAttendanceListForActivity(a)` → `window.open('/public/attendance-list/<public_slug>', '_blank')`
  dentro del gesto del usuario (evita el bloqueador de popups); si la pestaña
  se bloquea, navega en la misma pestaña. Usa **solo `public_slug`** (no `id`);
  si la actividad no lo tiene, muestra un toast y no hace nada.
  A diferencia del admin, **no** hace `fetch` + blob: la ruta no exige header
  `Authorization`.
- `downloadRegistrationsForActivity(a)` → `POST /api/public/registrations/export` (XLSX).

Etiquetas de los botones por actividad (`event_registrations_public.html`):

- **Imprimir** (índigo, `ti-printer`) → lista imprimible.
- **XLSX** (gris, `ti-file-spreadsheet`) → descarga de datos. Antes estaba
  etiquetado "Lista", lo que confundía con la lista imprimible.

En la vista pública por actividad (`registrations_public.html`) el botón de
descarga también pasó de "Lista" a **XLSX**.

## Seguridad

- La ruta es pública a propósito: es la que usan los Jefes de Carrera desde el
  enlace del evento/actividad.
- **Solo acepta `public_slug`** (sin fallback a ID numérico): así se cierra el
  volcado enumerable `/public/attendance-list/1`, `/2`, ... El alcance queda en
  "quien tiene el enlace de la actividad".
- El admin (`/api/reports/attendance_list?activity_id=<id>`) sigue aceptando el
  ID numérico, pero exige JWT con rol Admin.
- **Residual conocido**: `GET /api/public/registrations?activity_id=` (el que
  alimenta la propia vista de Jefes) y `POST /api/public/registrations/export`
  siguen resolviendo por ID numérico. Si quieres cerrarlos igual, hay que
  replicar el filtro de slug en esos endpoints (queda fuera de este alcance).

## Tests

- Backend: `tests/api/test_public_attendance_list.py`
  (404 por referencia inválida, render sin JWT por slug, **404 por ID
  numérico** y por actividad sin `public_slug`, igualdad con la salida de
  admin, columnas multiday).
- Frontend: `app/static/js/public/__tests__/event_registrations_public.print.test.js`
  (abre pestaña con `public_slug`, codificación en la URL, aviso cuando solo
  hay `id`, fallback si hay bloqueador, sin identificador).
