# Porcentaje de asistencia

Fórmula única que decide el porcentaje, el estado (`Asistió` / `Parcial` /
`Ausente`) y, en consecuencia, si el estudiante acredita horas.

- **Implementación**: `app/services/attendance_service.py::compute_attendance_metrics`
  (la llaman `calculate_attendance_percentage`, que persiste, y la vista previa
  de `POST /api/attendances/batch-checkout` en `dry_run`).
- **Tolerancia**: `app/services/self_register_service.py::arrival_tolerance_minutes`.
- **Tests**: `tests/test_attendance_percentage_tolerance.py` (matriz A–G),
  `tests/services/test_self_register_service.py`,
  `tests/api/test_batch_checkout.py`.

## 1. Fórmula

El denominador es **fijo** (la duración programada) para que nadie que hoy
acredita "Asistió" pueda bajar de categoría por un cambio de fórmula:

| Concepto   | Cálculo                                                      |
| ---------- | ------------------------------------------------------------ |
| presencia  | `\|[llegada, salida] ∩ [inicio, fin] programados\| − pausas` |
| perdón     | `min(max(0, llegada − inicio), tolerancia)`                  |
| crédito    | `min(duración programada, presencia + perdón)`               |
| porcentaje | `100 × crédito / duración programada`                        |

Estados: `>= 80%` → `Asistió`, `> 0%` → `Parcial`, `= 0%` → `Ausente`.
Regla dura previa: una **pausa igual o mayor que la duración** devuelve `0%`
(Ausente) antes de aplicar cualquier crédito.

## 2. Tolerancia de llegada (puerta == perdón)

```
tolerancia = min(public_self_register_close_minutes_after_start,   # tope, default 15
                 20% de la duración programada)                    # piso coherente
```

Un **solo número con dos caras**:

1. **Puerta**: cierra la ventana de auto-registro público
   (`self_register_window`), es decir hasta cuántos minutos después del inicio
   se puede escanear el QR de entrada.
2. **Crédito**: esos mismos minutos se perdonan en el porcentaje, de modo que
   quien llega dentro de la tolerancia y se queda hasta el final acredita
   **100%**, aunque el evento se cierre exactamente a la hora programada.

El 20% evita que la tolerancia contradiga el umbral del 80%: para llegar al
80% de una conferencia de 60 min el límite matemático es llegar 12 min tarde,
así que allí mandan 12 y no 15; en un taller de 4 h manda el tope (15).

> El perdón es **incondicional** (no exige haber llegado hasta el final): una
> salida temprana sigue descontando presencia, pero el retraso no se cobra dos
> veces.

## 3. Llegada real: `attendances.arrival_time`

`check_in_time` **no sirve para medir el atraso**: `resume_attendance()` pliega
cada pausa desplazando el `check_in_time` (ver
`docs/PAUSE_RESUME_ATTENDANCE.md`), así que una fila con pausas parecería que
llegó tarde cuando en realidad llegó temprano.

Por eso la fila guarda la llegada en `attendances.arrival_time` (nullable):

- Se llena sola en el **primer check-in** mediante listeners
  `before_insert` / `before_update` (`app/models/attendance.py`), por lo que
  cubre los ~14 puntos del código que asignan `check_in_time` sin tocarlos.
- Después **no se toca nunca**: ni los pliegues de pausa ni una corrección
  manual posterior cambian la primera llegada.
- **Filas viejas** (sin `arrival_time`): se usa el **menor** de `created_at` y
  `check_in_time` — cota conservadora que nunca inventa un atraso. Conviene
  correr el backfill de `created_at`
  (`tools/backfill_attendance_created_at_local.py`) para que esas filas midan
  bien.

## 4. Tope en el fin programado y `activities.actual_end_datetime`

El crédito se recorta a `min(duración programada, …)`, así que un evento que
se desborda **no genera porcentaje extra ni rescata pausas**: si alguien se fue
20 min antes, esos 20 min siguen descontando aunque la actividad haya
terminado 40 min tarde.

La hora real de cierre sí se registra, como **dato informativo**, en
`activities.actual_end_datetime`:

- Se escribe desde el modal **Batch checkout** (`actual_end_time` en el
  payload) y se ecoa en `summary.actual_end_time` / `summary.actual_end_saved`.
- En `dry_run` sólo se ecoa el valor, no se persiste.
- No entra en ningún cálculo.

## 5. Matriz de escenarios (conferencia de 60 min, tolerancia 12)

| #   | Escenario                                         | Resultado                                     |
| --- | ------------------------------------------------- | --------------------------------------------- |
| A   | Llega 10:00, se va 11:00                          | 100% `Asistió`                                |
| B   | Llega 10:12, se va 11:00                          | 100% `Asistió`                                |
| B'  | Llega 10:30, se va 11:00                          | 70% `Parcial` (sólo se perdonan 12)           |
| C   | Llega 10:00, pausa 20 min, se va 11:20 (desborde) | 66.67% `Parcial`                              |
| C'  | Llega 10:10, pausa 20 min, se va 11:00            | 66.67% `Parcial` (sólo el retraso se perdona) |
| D   | Llega 10:10, se va 11:10 (desfase compensado)     | 100% `Asistió`                                |
| E   | Llega 10:12, se va 10:55                          | 91.67% `Asistió`                              |
| F   | Llega 10:00, se va 10:55                          | 91.67% `Asistió` (igual que siempre)          |
| G   | Pausa ≥ 60 min                                    | 0% `Ausente`                                  |

Nota sobre el umbral del 80% en una conferencia de 60 min: con el perdón de
12 min, llegar hasta 24 min tarde y quedarse al final sigue acreditando
(`72 − atraso >= 48`). El gate de 12 min sólo restringe al **auto-registro
público**; un walk-in o un alta manual por parte del admin puede superarlo y
llegar hasta 24 min.

## 6. Despliegue

1. **Migración**: `alembic upgrade head`
   (`20261007_add_arrival_time_and_actual_end` agrega
   `attendances.arrival_time` y `activities.actual_end_datetime`).
2. **Setting**: el default pasó de `20` a `15`. Si la fila ya existe en
   `app_settings`, hay que actualizarla en `Admin → Settings` (el seed
   `scripts/initialize_app_settings.py` sólo inserta faltantes):
   `UPDATE app_settings SET value='15', default_value='15' WHERE key='public_self_register_close_minutes_after_start';`
3. **Backfill pendiente** (relacionado, ver `docs/TIMEZONE_FIX.md`):
   `python tools/backfill_attendance_created_at_local.py --verbose` y luego
   `--apply`. Afecta el fallback de `arrival_time` descrito en §3.
4. **Recálculo**: los porcentajes se recalculan al hacer checkout / batch
   checkout de cada actividad. Sólo pueden subir (el perdón es aditivo y el
   crédito está techo al 100%), así que nadie pierde la `Asistió` que ya
   tenía.
