# Lista de asistencia imprimible (admin + vista pública de Jefes)

Dos rutas renderizan **la misma** lista de preregistrados de una actividad,
lista para imprimir:

| Ruta                                                | Autenticación     | Uso                                                            |
| --------------------------------------------------- | ----------------- | -------------------------------------------------------------- |
| `GET /api/reports/attendance_list?activity_id=<id>` | JWT + rol Admin   | Panel admin → Reportes → "4. Lista de asistencia (imprimible)" |
| `GET /public/attendance-list/<activity_ref>`        | Ninguna (pública) | Vista de Jefes de Carrera → botón **Imprimir**                 |

`activity_ref` se resuelve **slug primero** (`activity.public_slug`) y **ID
numérico como fallback**, igual que el resto de las vistas públicas.

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

- `printAttendanceListForActivity(a)` → `window.open('/public/attendance-list/<slug|id>', '_blank')`
  dentro del gesto del usuario (evita el bloqueador de popups); si la pestaña
  se bloquea, navega en la misma pestaña.
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

La ruta pública no expone datos nuevos: la vista de Jefes de Carrera ya lista
esos mismos preregistros con el slug/ID de la actividad
(`/api/public/registrations?activity_id=...`). El alcance sigue siendo
"quien tiene el enlace del evento/actividad".

## Tests

- Backend: `tests/api/test_public_attendance_list.py`
  (404 por referencia inválida, render sin JWT por slug e ID, igualdad con la
  salida de admin, columnas multiday).
- Frontend: `app/static/js/public/__tests__/event_registrations_public.print.test.js`
  (abre pestaña con ID/slug, fallback si hay bloqueador, sin identificador).
