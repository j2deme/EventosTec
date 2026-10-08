"""
Corrige `attendances.created_at` / `updated_at` de hora UTC a hora local.

Contexto (ver `docs/TIMEZONE_FIX.md`): hasta la corrección del modelo
`Attendance` (fix de escritura) esas columnas se escribían con
`db.func.now()`, es decir el **reloj de MySQL (UTC)**, mientras que el resto
de la app guarda **wall time local** (`America/Mexico_City`). Como el admin
muestra esa columna como "Fecha registro", salía +6 h (13:19 reales → 19:19).

Cómo distingue una fila mala de una buena
------------------------------------------
Una marca temporal por sí sola no basta (una fila vieja guarda la hora UTC del
servidor y una nueva la hora local: mismo formato, distinto significado), así
que cada fila se clasifica con señales:

  utc_confirmed   Señal aritmética: `created_at = check_in_time + desfase`
                  (check-in ya local, columna aún en UTC), o prueba de
                  ventana: `created_at` cae FUERA del horario de la actividad
                  mientras `created_at - desfase` cae DENTRO. Se corrige.
  local_confirmed Lo contrario (o `created_at = check_in_time - desfase`):
                  la fila ya está en hora local. NO se corrige.
  ambiguous       Sin señal: falta `check_in_time` o el horario no decide
                  (ambas interpretaciones caben). Se corrige por DEFECTO
                  porque la columna **solo** se escribió con `db.func.now()`
                  (ningún código asigna `created_at`); usa `--strict` para
                  dejarlas fuera.
  post_cutoff     `created_at > --cutoff`: posterior al momento de corrección.
                  NO se corrige.

Uso (desde la raíz del proyecto, con el virtualenv activo):

  # 1) Reporte (dry-run): clasifica y NO escribe nada
  python tools/backfill_attendance_created_at_local.py --verbose

  # 2) Corrección (una sola vez)
  python tools/backfill_attendance_created_at_local.py --apply

  # 3) Solo las filas con señal dura
  python tools/backfill_attendance_created_at_local.py --apply --strict

**Orden recomendado**: ejecutar este tool ANTES de desplegar el fix de
escritura (o pasando `--cutoff` con la hora exacta del despliegue). Después
del despliegue empiezan a llegar filas ya en hora local y solo el corte las
separa de las viejas.

El resultado queda marcado en `app_settings`
(`backfill_attendance_created_at_local_applied_at`) para que una segunda
corrida no reste el desfase dos veces; `--force` lo ignora.

Opciones:
  --cutoff "YYYY-MM-DD HH:MM:SS"  Tope en hora UTC. Default: ahora.
  --strict                        Corregir solo `utc_confirmed`.
  --columns created_at,updated_at Columnas a corregir (default: ambas).
  --force                         Ignora la marca de "ya aplicado".
  --limit N                       Filas de ejemplo a imprimir por clase.
  --verbose                       Imprime las filas clasificadas.

Se recomienda respaldo de la BD antes de `--apply`.
"""

import argparse
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

# Asegurar que la raíz del proyecto esté en sys.path (patrón del repo, ver
# AGENTS.md) para que `from app import ...` funcione al invocar el script
# desde cualquier directorio.
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

try:
    from app import create_app, db
    from app.models.activity import Activity
    from app.models.app_setting import AppSetting
    from app.models.attendance import Attendance
    from app.services.settings_manager import AppSettings
    from app.utils.datetime_utils import app_timezone_info
except Exception as exc:
    print("Error importing app package:", file=sys.stderr)
    print(str(exc), file=sys.stderr)
    print("\nDiagnostic info:", file=sys.stderr)
    try:
        print("cwd=", os.getcwd(), file=sys.stderr)
        print("proj_root=", proj_root, file=sys.stderr)
        print("sys.path sample:", file=sys.stderr)
        for p in sys.path[:10]:
            print("  " + repr(p), file=sys.stderr)
        print("\nproj_root contents (top 20):", file=sys.stderr)
        for i, name in enumerate(sorted(os.listdir(proj_root))[:20]):
            print(f"  {i + 1}. {name}", file=sys.stderr)
    except Exception:
        print("Error gathering diagnostic info", file=sys.stderr)
        traceback.print_exc()
    raise

MARKER_KEY = "backfill_attendance_created_at_local_applied_at"

# Tolerancia para "misma hora": el INSERT y el check-in ocurren casi juntos,
# pero no en el mismo evento de SQL, así que se permiten unos minutos.
TOLERANCE = timedelta(minutes=5)

# Ventana en la que un check-in es plausible: desde 3 h antes del inicio hasta
# 1 h después del fin. Con un desfase de 6 h, para actividades cortas la
# ventana local y la desplazada no se solapan y eso permite decidir.
EARLY_GRACE = timedelta(hours=3)
LATE_GRACE = timedelta(hours=1)

# Por defecto se corrige lo que no esté probado que ya está en hora local:
# señal dura (`utc_confirmed`) + sin señal (`ambiguous`, la columna solo se
# escribió con `db.func.now()`). `--strict` deja solo la señal dura.
DEFAULT_CLASSES = ("utc_confirmed", "ambiguous")
STRICT_CLASSES = ("utc_confirmed",)


def local_offset_hours(naive_wall: datetime, tz_name: str) -> float:
    """Horas que hay que restar a una hora UTC para obtener la hora local."""
    aware_utc = naive_wall.replace(tzinfo=timezone.utc)
    local = aware_utc.astimezone(app_timezone_info(tz_name))
    return (aware_utc.utcoffset() - local.utcoffset()).total_seconds() / 3600.0


def in_window(value, window):
    """¿`value` cae en la ventana horaria de la actividad?"""
    if window is None or value is None:
        return None
    start, end = window
    if start is None or end is None:
        return None
    return (start - EARLY_GRACE) <= value <= (end + LATE_GRACE)


def classify(created, check_in, off_hours, cutoff, window=None):
    """Clasifica un `created_at` de la BD.

    Args:
        created: valor almacenado de `created_at` (naive).
        check_in: `check_in_time` almacenado (naive) o None.
        off_hours: horas a restar para pasar de UTC a hora local (p. ej. 6).
        cutoff: `created_at` máximo a considerar (naive, hora UTC).
        window: tupla `(start, end)` de la actividad en hora local o None.

    Returns:
        (clase, motivo)
    """
    off = timedelta(hours=off_hours)

    if created > cutoff:
        return ("post_cutoff", "posterior al corte")

    # 1) Señal aritmética contra el check-in.
    if check_in is not None:
        delta = created - check_in
        if abs(delta - off) <= TOLERANCE:
            return (
                "utc_confirmed",
                f"created_at = check_in_time + {off_hours:g} h "
                "(check-in local, columna en UTC)",
            )
        if abs(delta + off) <= TOLERANCE:
            return (
                "local_confirmed",
                f"created_at = check_in_time - {off_hours:g} h: ya en hora local",
            )

    # 2) Prueba de ventana contra el horario de la actividad.
    inside = in_window(created, window)
    shifted_inside = in_window(created - off, window)
    if inside is not None and shifted_inside is not None:
        if inside and not shifted_inside:
            return (
                "local_confirmed",
                "created_at cae dentro de la ventana de la actividad",
            )
        if shifted_inside and not inside:
            return (
                "utc_confirmed",
                f"created_at - {off_hours:g} h cae dentro de la ventana "
                "de la actividad",
            )

    # 3) Sin señal suficiente.
    if check_in is None:
        motivo = "sin check_in_time"
    elif abs(created - check_in) <= TOLERANCE:
        motivo = "mismo reloj que check_in_time (UTC antes del 2026-10-06)"
    else:
        motivo = f"diferencia con check_in_time no reconocida ({created - check_in})"
    if inside is None:
        motivo += "; sin ventana de actividad"
    else:
        motivo += "; ambas interpretaciones en la ventana"
    return ("ambiguous", motivo)


def should_fix(cls: str, apply_classes) -> bool:
    """¿La clase entra en el conjunto que se va a corregir?"""
    return cls in apply_classes


def get_marker():
    return AppSetting.find_by_key(MARKER_KEY)


def write_marker(summary: str):
    setting = get_marker()
    if setting is None:
        setting = AppSetting(key=MARKER_KEY)
        db.session.add(setting)
    setting.value = summary
    setting.description = (
        "Marca de la corrección UTC→local de attendances.created_at/"
        "updated_at (tools/backfill_attendance_created_at_local.py). "
        "Evita dobles corridas: volver a aplicar restaría 6 h dos veces."
    )
    setting.data_type = "string"
    setting.is_editable = False
    db.session.commit()


def parse_cutoff(raw):
    if raw is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise SystemExit(f"--cutoff inválido: {raw!r} (usa 'YYYY-MM-DD HH:MM:SS')")


def run(args):
    # La consola de Windows (cp1252) no sabe imprimir "→": salir en UTF-8 con
    # errores reemplazados para que el reporte no truene a media corrida.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    app = create_app()
    with app.app_context():
        cutoff = parse_cutoff(args.cutoff)
        tz_name = AppSettings.app_timezone()

        columns = [c.strip() for c in args.columns.split(",") if c.strip()]
        bad_cols = [c for c in columns if c not in ("created_at", "updated_at")]
        if bad_cols:
            raise SystemExit(f"--columns inválido(s): {', '.join(bad_cols)}")

        apply_classes = set(c.strip() for c in args.classes.split(",") if c.strip())
        if getattr(args, "strict", False):
            apply_classes = set(STRICT_CLASSES)

        marker = get_marker()
        if marker is not None and args.apply and not args.force:
            raise SystemExit(
                "Esta corrección ya fue aplicada "
                f"({marker.value}). Volver a ejecutarla restaría el desfase "
                "dos veces. Usa --force solo si estás seguro de que la marca "
                "no corresponde a una corrida real."
            )

        activities = {a.id: a for a in Activity.query.all()}

        rows = Attendance.query.order_by(Attendance.id).all()
        stats = {}
        to_fix = []
        ci_also_utc = 0

        for row in rows:
            act = activities.get(row.activity_id)
            window = (act.start_datetime, act.end_datetime) if act is not None else None
            off_hours = local_offset_hours(row.created_at, tz_name)
            cls, reason = classify(
                row.created_at, row.check_in_time, off_hours, cutoff, window
            )
            fix = should_fix(cls, apply_classes)

            # Filas antiguas: `check_in_time` está en el mismo reloj que
            # `created_at`, así que también es hora UTC. No se toca (los
            # eventos pasados ya están cerrados), pero se reporta.
            if (
                cls == "utc_confirmed"
                and row.check_in_time is not None
                and abs(row.created_at - row.check_in_time) <= TOLERANCE
            ):
                ci_also_utc += 1

            bucket = stats.setdefault(cls, {"total": 0, "fix": 0, "sample": []})
            bucket["total"] += 1
            if fix:
                bucket["fix"] += 1
            if len(bucket["sample"]) < max(args.limit, 3):
                bucket["sample"].append(
                    (row.id, row.created_at, row.check_in_time, window, reason, fix)
                )
            if fix:
                to_fix.append((row, off_hours, columns))

        print("=" * 78)
        print("Corrección UTC → hora local: attendances.created_at / updated_at")
        print(f"  zona de la app : {tz_name}")
        print(f"  corte (UTC)    : {cutoff:%Y-%m-%d %H:%M:%S}")
        print(f"  columnas       : {', '.join(columns)}")
        print(f"  filas          : {len(rows)}")
        print(f"  clases a corregir: {', '.join(sorted(apply_classes))}")
        if marker is not None:
            print(f"  marca previa   : {marker.value}")
        print("=" * 78)

        for cls in sorted(stats):
            info = stats[cls]
            print(f"{cls:18} {info['total']:6} filas  → corregir: {info['fix']}")
            if args.verbose:
                for rid, created, ci, window, reason, fix in info["sample"]:
                    ventana = (
                        f"{window[0]} → {window[1]}" if window and window[0] else "—"
                    )
                    print(
                        f"    id={rid} created_at={created} check_in={ci}\n"
                        f"      actividad={ventana}\n"
                        f"      {'CORREGIR' if fix else 'no tocar'}: {reason}"
                    )

        print("-" * 78)
        print(f"Total a corregir: {len(to_fix)}")
        if ci_also_utc:
            print(
                f"Nota: {ci_also_utc} fila(s) tienen también `check_in_time` "
                "en hora UTC (escritas antes del fix del 2026-10-06). Esa "
                "columna NO se toca aquí: los eventos pasados ya están "
                "cerrados y recalcularlos cambiaría los porcentajes."
            )
        if not args.apply:
            print("Dry run: no se modificó nada. Repite con --apply para corregir.")
            return 0

        if not to_fix:
            print("Nada que corregir.")
            return 0

        shifted = 0
        skipped_updated = 0
        for row, off_hours, cols in to_fix:
            delta = timedelta(hours=off_hours)
            created_orig = row.created_at
            for col in cols:
                value = getattr(row, col)
                if value is None:
                    continue
                # `updated_at` solo se corrige si está en el mismo reloj que
                # `created_at` (fila sin editar). Si difiere, pudo escribirse
                # después del fix de escritura y ya es hora local.
                if col == "updated_at" and abs(value - created_orig) > TOLERANCE:
                    skipped_updated += 1
                    continue
                setattr(row, col, value - delta)
                shifted += 1
        db.session.commit()

        summary = (
            f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | "
            f"cutoff={cutoff:%Y-%m-%d %H:%M:%S} UTC | "
            f"filas={len(to_fix)} | campos={shifted} | "
            f"clases={','.join(sorted(apply_classes))} | tz={tz_name}"
        )
        write_marker(summary)
        print(f"Aplicado: {len(to_fix)} filas, {shifted} campos modificados.")
        if skipped_updated:
            print(
                f"  `updated_at` no corregido en {skipped_updated} fila(s) "
                "(difiere de created_at: pudo escribirse ya en hora local)."
            )
        print(f"Marca registrada en app_settings[{MARKER_KEY}]: {summary}")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Corrige attendances.created_at/updated_at de UTC a hora local"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Escribir los cambios (default: dry run)"
    )
    parser.add_argument(
        "--cutoff",
        default=None,
        help="Tope en hora UTC ('YYYY-MM-DD HH:MM:SS'). Default: ahora.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Corregir solo las filas con señal dura (utc_confirmed)",
    )
    parser.add_argument(
        "--classes",
        default=",".join(DEFAULT_CLASSES),
        help="Clases a corregir con --apply (default: utc_confirmed,ambiguous)",
    )
    parser.add_argument(
        "--columns",
        default="created_at,updated_at",
        help="Columnas a corregir",
    )
    parser.add_argument("--limit", type=int, default=5, help="Ejemplos por clase")
    parser.add_argument("--verbose", action="store_true", help="Imprime ejemplos")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignora la marca de corrida aplicada (¡puede duplicar el ajuste!)",
    )
    args = parser.parse_args()
    try:
        sys.exit(run(args))
    except SystemExit:
        raise
    except Exception:
        print("Error while running backfill", file=sys.stderr)
        raise
