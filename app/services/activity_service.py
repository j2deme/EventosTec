from datetime import timezone
from flask import current_app
from app.utils.datetime_utils import localize_naive_datetime, safe_iso
from app import db
from app.models.activity import Activity
from app.models.event import Event
from marshmallow import ValidationError
import json
from io import BytesIO
try:
    import pandas as pd
except Exception:
    pd = None
import unicodedata
import difflib
import re
from datetime import datetime
from app.utils.slug_utils import slugify, generate_unique_slug


def validate_activity_dates(activity_data):
    """
    Valida que las fechas de la actividad estén dentro del rango del evento.

    Args:
        activity_data (dict): Datos de la actividad a validar

    Raises:
        ValidationError: Si las fechas no son válidas
    """
    try:
        event_id = activity_data.get('event_id')
        start_datetime = activity_data.get('start_datetime')
        end_datetime = activity_data.get('end_datetime')

        # Asegurar que las fechas sean timezone-aware: interpretar datetimes
        # naive usando APP_TIMEZONE y convertir a UTC
        app_timezone = current_app.config.get(
            'APP_TIMEZONE', 'America/Mexico_City')
        if start_datetime is not None:
            start_datetime = localize_naive_datetime(
                start_datetime, app_timezone)
        if end_datetime is not None:
            end_datetime = localize_naive_datetime(end_datetime, app_timezone)

        if not event_id:
            raise ValidationError('El evento es requerido')

        event = db.session.get(Event, event_id)
        if not event:
            raise ValidationError('Evento no encontrado')

        # Asegurar que las fechas del evento sean timezone-aware
        event_start = event.start_date
        event_end = event.end_date
        app_timezone = current_app.config.get(
            'APP_TIMEZONE', 'America/Mexico_City')
        if event_start is not None:
            event_start = localize_naive_datetime(event_start, app_timezone)
        if event_end is not None:
            event_end = localize_naive_datetime(event_end, app_timezone)

        if start_datetime and event_start is not None and event_end is not None and (start_datetime < event_start or start_datetime > event_end):
            raise ValidationError(
                'La fecha de inicio de la actividad debe estar dentro del rango del evento')

        if end_datetime and event_start is not None and event_end is not None and (end_datetime < event_start or end_datetime > event_end):
            raise ValidationError(
                'La fecha de fin de la actividad debe estar dentro del rango del evento')

        if start_datetime and end_datetime and start_datetime > end_datetime:
            raise ValidationError(
                'La fecha de inicio no puede ser posterior a la fecha de fin')

    except KeyError as e:
        raise ValidationError(f'Campo requerido faltante: {str(e)}')
    except ValueError as e:
        raise ValidationError(f'Formato de fecha inválido: {str(e)}')


def create_activity(activity_data):
    """
    Crea una nueva actividad con validaciones.

    Args:
        activity_data (dict): Datos de la actividad

    Returns:
        Activity: La actividad creada

    Raises:
        ValidationError: Si los datos no son válidos
    """
    # Validar fechas
    validate_activity_dates(activity_data)

    # Asegurar que las fechas sean timezone-aware: interpretar naive en APP_TIMEZONE
    app_timezone = current_app.config.get(
        'APP_TIMEZONE', 'America/Mexico_City')
    if 'start_datetime' in activity_data and activity_data['start_datetime'] is not None:
        activity_data['start_datetime'] = localize_naive_datetime(
            activity_data['start_datetime'], app_timezone)
    if 'end_datetime' in activity_data and activity_data['end_datetime'] is not None:
        activity_data['end_datetime'] = localize_naive_datetime(
            activity_data['end_datetime'], app_timezone)

    # Calcular duración si no se proporciona
    if 'duration_hours' not in activity_data or activity_data['duration_hours'] is None:
        start = activity_data['start_datetime']
        end = activity_data['end_datetime']
        activity_data['duration_hours'] = (end - start).total_seconds() / 3600

    # Serializar campos JSON si vienen como estructuras Python
    if 'speakers' in activity_data and activity_data['speakers'] is not None:
        try:
            if not isinstance(activity_data['speakers'], str):
                activity_data['speakers'] = json.dumps(
                    activity_data['speakers'])
            else:
                json.loads(activity_data['speakers'])
        except Exception:
            raise ValidationError('Campo speakers debe ser JSON serializable')

    if 'target_audience' in activity_data and activity_data['target_audience'] is not None:
        try:
            if not isinstance(activity_data['target_audience'], str):
                activity_data['target_audience'] = json.dumps(
                    activity_data['target_audience'])
            else:
                json.loads(activity_data['target_audience'])
        except Exception:
            raise ValidationError(
                'Campo target_audience debe ser JSON serializable')

    # Crear la actividad de forma explícita para evitar pasar un dict
    # directamente al constructor (mejora la trazabilidad y evita
    # advertencias del analizador estático).
    activity = Activity()
    for key, value in activity_data.items():
        setattr(activity, key, value)

    # Handle public_slug: if not provided, generate from name
    try:
        if not getattr(activity, 'public_slug', None):
            # generate a unique slug based on activity name
            base_name = getattr(activity, 'name', '') or ''
            if base_name:
                activity.public_slug = generate_unique_slug(
                    db.session, Activity, base_name, column='public_slug')
    except Exception:
        # best-effort: leave public_slug as None on failure
        pass

    db.session.add(activity)
    db.session.commit()

    return activity


def update_activity(activity_id, activity_data):
    """
    Actualiza una actividad existente con validaciones.

    Args:
        activity_id (int): ID de la actividad
        activity_data (dict): Datos actualizados

    Returns:
        Activity: La actividad actualizada

    Raises:
        ValidationError: Si los datos no son válidos
    """
    # Obtener actividad existente
    activity = db.session.get(Activity, activity_id)
    if not activity:
        raise ValidationError('Actividad no encontrada')

    # Si se están actualizando fechas, validar
    if 'start_datetime' in activity_data or 'end_datetime' in activity_data or 'event_id' in activity_data:
        # Combinar datos existentes con nuevos para validación
        validation_data = {
            'event_id': activity_data.get('event_id', activity.event_id),
            'start_datetime': activity_data.get('start_datetime', activity.start_datetime),
            'end_datetime': activity_data.get('end_datetime', activity.end_datetime)
        }
        validate_activity_dates(validation_data)

    # Asegurar que las fechas sean timezone-aware si se actualizan
    app_timezone = current_app.config.get(
        'APP_TIMEZONE', 'America/Mexico_City')
    if 'start_datetime' in activity_data and activity_data['start_datetime'] is not None:
        activity_data['start_datetime'] = localize_naive_datetime(
            activity_data['start_datetime'], app_timezone)
    if 'end_datetime' in activity_data and activity_data['end_datetime'] is not None:
        activity_data['end_datetime'] = localize_naive_datetime(
            activity_data['end_datetime'], app_timezone)

    if 'duration_hours' in activity_data and activity_data['duration_hours'] is not None:
        start_dt = activity_data.get('start_datetime', activity.start_datetime)
        end_dt = activity_data.get('end_datetime', activity.end_datetime)
        duration = activity_data['duration_hours']

        if start_dt and end_dt:
            calculated_duration = (end_dt - start_dt).total_seconds() / 3600
            if not (0 < duration <= calculated_duration):
                raise ValidationError(
                    f'La duración proporcionada ({duration} horas) debe ser mayor que 0 y menor o igual a la duración calculada a partir de las fechas ({calculated_duration:.2f} horas).'
                )

    for key, value in activity_data.items():
        # Serializar JSON fields cuando se actualizan
        if key == 'speakers' and value is not None:
            try:
                if not isinstance(value, str):
                    value = json.dumps(value)
                else:
                    json.loads(value)
            except Exception:
                raise ValidationError(
                    'Campo speakers debe ser JSON serializable')

        if key == 'target_audience' and value is not None:
            try:
                if not isinstance(value, str):
                    value = json.dumps(value)
                else:
                    json.loads(value)
            except Exception:
                raise ValidationError(
                    'Campo target_audience debe ser JSON serializable')

        setattr(activity, key, value)
    # Special handling for public_slug when name changes
    try:
        # If name changed in payload
        if 'name' in activity_data:
            new_name = activity_data.get('name')
            # canonical slug for new name
            canonical_new = slugify(new_name or '')

            current_slug = getattr(activity, 'public_slug', None)

            # If there was no slug, generate one automatically
            if not current_slug:
                if new_name:
                    activity.public_slug = generate_unique_slug(
                        db.session, Activity, new_name, column='public_slug')
            else:
                # If current_slug equals canonical slug generated from previous name,
                # then it wasn't manually edited -> update it to new canonical + uniqueness
                # To detect previous canonical, compute from previous name by reversing: we don't have previous name here,
                # so detect manual edit by comparing current_slug to slugify(new_name) and slugify(old_name) not available.
                # Simpler heuristics: if current_slug == slugify(new_name) -> leave as is; if current_slug != slugify(new_name)
                # and payload contains flag 'apply_generated_slug'==True, then replace; otherwise keep current_slug.
                apply_flag = bool(activity_data.get(
                    'apply_generated_slug', False))
                if apply_flag and new_name:
                    activity.public_slug = generate_unique_slug(
                        db.session, Activity, new_name, column='public_slug')
                # else: honor manual slug (do nothing)
    except Exception:
        # ignore slug generation failures and proceed with commit
        pass

    db.session.commit()
    return activity


def create_activities_from_xlsx(file_stream, event_id=None, dry_run=True):
    """
    Parse an XLSX (first sheet) and create activities in batch.

    Expected headers (case-insensitive):
      department,name,description,start_datetime,end_datetime,duration_hours,
      activity_type,location,modality,requirements,knowledge_area,speakers,
      target_general,target_careers,max_capacity

    speakers cell may be a JSON array or a semicolon-separated list of entries
    where each entry is degree|name|organization or name only.

    Returns a dict: { created: int, errors: [{row: n, message: str, data: {}}], rows: parsed_rows }
    """
    if pd is None:
        raise RuntimeError(
            'pandas is required for XLSX import (install pandas and openpyxl)')

    # Ensure stream pointer at start
    try:
        file_stream.seek(0)
    except Exception:
        pass

    # Use pandas to read the first sheet into a DataFrame
    try:
        # pandas will use openpyxl engine for .xlsx by default when available
        df = pd.read_excel(BytesIO(file_stream.read()),
                           sheet_name=0, engine='openpyxl')
    except Exception as e:
        return {'created': 0, 'errors': [{'row': 0, 'message': f'No se pudo leer el archivo: {e}'}], 'rows': []}

    if df.shape[0] == 0:
        return {'created': 0, 'errors': [{'row': 0, 'message': 'Archivo vacío o sin filas'}], 'rows': []}

    # Normalize header names: lowercase and strip
    # But accept headers in spanish: map common spanish headers to expected english field names
    def _normalize_raw(s):
        if s is None:
            return ''
        val = str(s).strip().lower()
        # normalize unicode (remove accents)
        val = unicodedata.normalize('NFD', val)
        val = ''.join(ch for ch in val if not unicodedata.combining(ch))
        # replace spaces and punctuation with underscore
        for ch in [' ', '-', '\t', '\n', '/']:
            val = val.replace(ch, '_')
        # remove parentheses and commas
        for ch in ['(', ')', ',', ':', ';', '.']:
            val = val.replace(ch, '')
        return val

    original_cols = list(df.columns)
    normalized = [_normalize_raw(c) for c in original_cols]

    # Map of common Spanish (normalized) -> English field names used by the schema
    spanish_map = {
        'departamento': 'department',
        'departamento_nombre': 'department',
        'nombre': 'name',
        'titulo': 'name',
        'descripcion': 'description',
        'objetivo': 'description',
        'fecha_inicio': 'start_datetime',
        'inicio': 'start_datetime',
        'hora_inicio': 'start_datetime',
        'fecha_fin': 'end_datetime',
        'fin': 'end_datetime',
        'hora_fin': 'end_datetime',
        'duracion': 'duration_hours',
        'duracion_horas': 'duration_hours',
        'actividad_tipo': 'activity_type',
        'tipo_actividad': 'activity_type',
        'tipo': 'activity_type',
        'lugar': 'location',
        'ubicacion': 'location',
        'modalidad': 'modality',
        'requisitos': 'requirements',
        'area_conocimiento': 'knowledge_area',
        'area': 'knowledge_area',
        'ponente': 'speakers',
        'ponentes': 'speakers',
        'oradores': 'speakers',
        'publico_general': 'target_general',
        'publico': 'target_general',
        'target_general': 'target_general',
        'carreras_objetivo': 'target_careers',
        'carreras': 'target_careers',
        'maximo': 'max_capacity',
        'capacidad_maxima': 'max_capacity',
        'capacidad': 'max_capacity',
        'max_capacity': 'max_capacity',
        'max_capacity_': 'max_capacity'
    }

    expected = [
        'department', 'name', 'description', 'start_datetime', 'end_datetime', 'duration_hours',
        'activity_type', 'location', 'modality', 'requirements', 'knowledge_area', 'speakers',
        'target_general', 'target_careers', 'max_capacity'
    ]

    # Build rename mapping
    renames = {}
    lookup_candidates = expected + list(spanish_map.keys())
    for orig, norm in zip(original_cols, normalized):
        target = None
        if norm in expected:
            target = norm
        elif norm in spanish_map:
            target = spanish_map[norm]
        else:
            # fuzzy match against known candidates
            match = difflib.get_close_matches(
                norm, lookup_candidates, n=1, cutoff=0.8)
            if match:
                m = match[0]
                if m in spanish_map:
                    target = spanish_map[m]
                else:
                    target = m

        if target and target != orig:
            renames[orig] = target

    if renames:
        df.rename(columns=renames, inplace=True)

    # Helper: parse composed activity date/time strings like
    # "[ 08 - OCT - 25 ] MIERCOLES / 11 a 13" or
    # "[ 08 - OCT - 25 ] MIERCOLES \nal\n[ 09 - OCT - 25 ] JUEVES / 11 A 15"
    def _parse_composed_date(s):
        if not s or not isinstance(s, str):
            return (None, None)

        # normalize whitespace
        txt = ' '.join(s.split())

        # find bracketed dates
        date_re = re.compile(
            r"\[\s*(\d{1,2})\s*-\s*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\s*-\s*(\d{2,4})\s*\]")
        dates = date_re.findall(txt)

        # map month names/abbrev (spanish + english) to month number
        month_map = {
            'ene': 1, 'enero': 1,
            'feb': 2, 'febrero': 2,
            'mar': 3, 'marzo': 3,
            'abr': 4, 'abril': 4,
            'may': 5, 'mayo': 5,
            'jun': 6, 'junio': 6,
            'jul': 7, 'julio': 7,
            'ago': 8, 'agosto': 8,
            'sep': 9, 'sept': 9, 'septiembre': 9,
            'oct': 10, 'octubre': 10,
            'nov': 11, 'noviembre': 11,
            'dic': 12, 'diciembre': 12
        }

        def _norm_month(m):
            m_clean = unicodedata.normalize('NFD', m).encode(
                'ascii', 'ignore').decode('ascii').lower()
            m_clean = re.sub(r'[^a-z]', '', m_clean)
            return month_map.get(m_clean)

        def _make_dt(d, mon, yr, hour=None, minute=0):
            try:
                y = int(yr)
                if y < 100:
                    y += 2000
                mnum = _norm_month(mon)
                if mnum is None:
                    return None
                day = int(d)
                if hour is None:
                    return datetime(y, mnum, day)
                else:
                    return datetime(y, mnum, day, int(hour), int(minute))
            except Exception:
                return None

        start_dt = None
        end_dt = None

        # find time range after a slash '/'
        time_part = None
        if '/' in txt:
            # take substring after last '/'
            time_part = txt.split('/')[-1].strip()
        else:
            # sometimes times are separated by ' / ' or ' a '
            # fallback: search for patterns like '11 a 13' anywhere
            time_part = txt

        # time regex: 11, 11:00, 11.00 optionally followed by separator (a,-,to) and second time
        time_re = re.compile(
            r"(\d{1,2})(?::(\d{2}))?\s*(?:a|-|to|–)\s*(\d{1,2})(?::(\d{2}))?", re.I)
        time_match = time_re.search(time_part or '')
        t1 = t2 = None
        if time_match:
            # Convert captured strings to ints defensively
            try:
                t1h = int(time_match.group(1))
            except Exception:
                t1h = None
            try:
                t1m = int(time_match.group(2)) if time_match.group(2) else 0
            except Exception:
                t1m = 0
            try:
                t2h = int(time_match.group(3))
            except Exception:
                t2h = None
            try:
                t2m = int(time_match.group(4)) if time_match.group(4) else 0
            except Exception:
                t2m = 0
            t1 = (t1h, t1m)
            t2 = (t2h, t2m)

        if len(dates) >= 1:
            d0 = dates[0]
            start_dt = _make_dt(d0[0], d0[1], d0[2], t1[0]
                                if t1 else None, t1[1] if t1 else 0)
            if len(dates) >= 2:
                d1 = dates[1]
                end_dt = _make_dt(d1[0], d1[1], d1[2], t2[0]
                                  if t2 else None, t2[1] if t2 else 0)
            else:
                # single day: if time range present, use t2 as end time on same day
                if t2:
                    end_dt = _make_dt(d0[0], d0[1], d0[2], t2[0], t2[1])
                else:
                    # no time range: leave end_dt as None
                    end_dt = None
        else:
            # Fallbacks when no bracketed dates were found.
            # 1) If the text contains a recognizable full date (yyyy-mm-dd or dd/mm/yyyy etc.), try pandas parsing
            try:
                if pd is not None:
                    parsed = pd.to_datetime(txt, errors='coerce')
                    if parsed is not None and not pd.isna(parsed):
                        # parsed may include time; convert to python datetime
                        if hasattr(parsed, 'to_pydatetime'):
                            base_dt = parsed.to_pydatetime()
                        else:
                            try:
                                base_dt = parsed
                            except Exception:
                                base_dt = None

                        if base_dt is not None:
                            # Apply detected time parts if present, otherwise keep parsed time
                            if t1 and t1[0] is not None:
                                t1h = int(t1[0])
                                t1m = int(t1[1]) if (t1[1] is not None) else 0
                                start_dt = datetime(
                                    base_dt.year, base_dt.month, base_dt.day, t1h, t1m)
                            else:
                                start_dt = base_dt

                            if t2 and t2[0] is not None:
                                t2h = int(t2[0])
                                t2m = int(t2[1]) if (t2[1] is not None) else 0
                                end_dt = datetime(
                                    base_dt.year, base_dt.month, base_dt.day, t2h, t2m)
                            else:
                                # If parsed included a time component and no explicit t2, keep parsed time as end_dt
                                end_dt = None
            except Exception:
                # ignore fallback failures
                pass
        return (start_dt, end_dt)

    parsed_rows = []
    errors = []
    created = 0

    # Detect if the DataFrame contains a column that should be treated as the
    # institution/organization value for speakers. We normalize column names
    # and look for anything containing 'instituc' (covers 'INSTITUCION',
    # 'Institución', etc.) or an explicit 'organizacion' header.
    institution_col = None
    for c in df.columns:
        try:
            if 'instituc' in _normalize_raw(c) or _normalize_raw(c) == 'organizacion':
                institution_col = c
                break
        except Exception:
            continue

    # Iterate rows preserving original Excel row numbers starting at 2 (header row 1)
    for idx, (_, row) in enumerate(df.iterrows(), start=2):
        try:
            # Convert row (Series) to dict; keep NaN as None
            rowdict = {k: (None if pd.isna(v) else v)
                       for k, v in row.to_dict().items()}

            # Coerce and normalize into activity_data
            activity_data = {}
            activity_data['event_id'] = int(
                event_id) if event_id is not None else None
            # Clean department field: take portion before '/' (e.g. "IAMB/05" -> "IAMB"), trim and uppercase
            raw_dept = rowdict.get('department')
            dept_str = str(raw_dept or '').strip()
            # If value contains '/', use the part before it
            if '/' in dept_str:
                dept_clean = dept_str.split('/')[0].strip()
            else:
                dept_clean = dept_str
            activity_data['department'] = dept_clean.upper()
            activity_data['name'] = str(rowdict.get('name') or '').strip()
            activity_data['description'] = rowdict.get('description')

            # Dates: pandas may parse to Timestamp or leave strings
            sd = rowdict.get('start_datetime')
            ed = rowdict.get('end_datetime')

            # Normalize pandas Timestamp, numpy datetime64, floats or strings to Python datetime
            try:
                # If pandas is available, use to_datetime with errors='coerce' to parse strings
                if pd is not None:
                    # pd.to_datetime handles Timestamps, numpy datetime64, and common string formats
                    parsed_sd = pd.to_datetime(
                        sd, errors='coerce') if sd not in (None, '') else None
                    parsed_ed = pd.to_datetime(
                        ed, errors='coerce') if ed not in (None, '') else None

                    if parsed_sd is not None and hasattr(parsed_sd, 'to_pydatetime'):
                        sd = parsed_sd.to_pydatetime()
                    elif pd.isna(parsed_sd):
                        sd = None

                    if parsed_ed is not None and hasattr(parsed_ed, 'to_pydatetime'):
                        ed = parsed_ed.to_pydatetime()
                    elif pd.isna(parsed_ed):
                        ed = None
                else:
                    # Fallback: if sd/ed are strings try fromisoformat or strptime
                    from app.utils.datetime_utils import parse_datetime_with_timezone
                    if isinstance(sd, str) and sd.strip() != '':
                        try:
                            sd = parse_datetime_with_timezone(sd)
                        except Exception:
                            sd = None
                    if isinstance(ed, str) and ed.strip() != '':
                        try:
                            ed = parse_datetime_with_timezone(ed)
                        except Exception:
                            ed = None
            except Exception:
                # Keep original sd/ed if normalization fails; schema validation will catch invalid types
                pass

            # If both sd/ed absent, try to find a composed date column (fecha_actividad, fechas, horario...)
            if sd in (None, '') and ed in (None, ''):
                # search for candidate keys in rowdict
                candidate_keys = []
                for k in rowdict.keys():
                    if not k:
                        continue
                    kn = _normalize_raw(k)
                    if any(sub in kn for sub in ('fecha', 'fechas', 'horario', 'horarios', 'fecha_actividad', 'horario_actividad')):
                        candidate_keys.append(k)

                composed_val = None
                if candidate_keys:
                    # prefer exact 'fecha_actividad' or 'fechas' if present
                    for prefer in ('fecha_actividad', 'fechas', 'horario', 'horarios', 'fechas_actividad'):
                        for k in candidate_keys:
                            if _normalize_raw(k) == prefer:
                                composed_val = rowdict.get(k)
                                break
                        if composed_val:
                            break
                    if composed_val is None:
                        composed_val = rowdict.get(candidate_keys[0])

                if composed_val:
                    parsed_sd, parsed_ed = _parse_composed_date(
                        str(composed_val))
                    sd = parsed_sd or sd
                    ed = parsed_ed or ed

            # If sd/ed are datetime-like, convert to ISO strings so Marshmallow DateTime loader parses them reliably.
            # use centralized safe_iso from app.utils.datetime_utils

            activity_data['start_datetime'] = safe_iso(sd)
            activity_data['end_datetime'] = safe_iso(ed)

            dur_val = rowdict.get('duration_hours')
            if dur_val not in (None, ''):
                try:
                    activity_data['duration_hours'] = float(str(dur_val))
                except Exception:
                    activity_data['duration_hours'] = None

            activity_data['activity_type'] = rowdict.get('activity_type') or ''
            activity_data['location'] = rowdict.get('location') or 'N/A'
            activity_data['modality'] = rowdict.get('modality') or 'Presencial'
            activity_data['requirements'] = rowdict.get('requirements')
            activity_data['knowledge_area'] = rowdict.get('knowledge_area')

            # Speakers parsing: accept JSON string or semicolon-separated list.
            # If an 'INSTITUCION'/'organizacion' column is present in the sheet,
            # use its value as the 'organization' for any speaker entries that
            # don't include an organization.
            speakers_cell = rowdict.get('speakers')
            speakers = []
            # institution value for this row (after NaN->None conversion above)
            inst_val = None
            if institution_col:
                inst_val = rowdict.get(institution_col)
                # coerce to str if not None
                if inst_val is not None:
                    try:
                        inst_val = str(inst_val).strip()
                    except Exception:
                        pass

            if speakers_cell:
                # Try JSON first
                def _append_speaker(name, degree, org):
                    try:
                        n = str(name).strip()
                    except Exception:
                        n = ''
                    try:
                        d = str(degree).strip()
                    except Exception:
                        d = ''
                    try:
                        o = str(org).strip() if org is not None else ''
                    except Exception:
                        o = ''
                    if not o and inst_val:
                        o = inst_val
                    speakers.append(
                        {'name': n, 'degree': d, 'organization': o})

                parsed_json = None
                if isinstance(speakers_cell, str) and speakers_cell.strip().startswith('['):
                    try:
                        parsed_json = json.loads(speakers_cell)
                    except Exception:
                        parsed_json = None

                if parsed_json and isinstance(parsed_json, list):
                    for sp in parsed_json:
                        if not isinstance(sp, dict):
                            _append_speaker(sp, '', inst_val)
                            continue
                        name = sp.get('name') or sp.get('nombre') or ''
                        degree = sp.get('degree') or sp.get('grado') or ''
                        org = sp.get('organization') or sp.get(
                            'organizacion') or sp.get('institucion') or ''
                        _append_speaker(name, degree, org)
                else:
                    # Not JSON: split entries. Prefer ';' but fallback to ',' when no ';' present
                    if isinstance(speakers_cell, str):
                        if ';' in speakers_cell:
                            entries = [p.strip() for p in speakers_cell.split(
                                ';') if p and str(p).strip()]
                        else:
                            # fallback to comma-separated entries (common in some sheets)
                            entries = [p.strip() for p in speakers_cell.split(
                                ',') if p and str(p).strip()]
                    else:
                        # Non-string: try to load as JSON anyway
                        try:
                            parsed = json.loads(speakers_cell)
                            entries = []
                            if isinstance(parsed, list):
                                for sp in parsed:
                                    if isinstance(sp, dict):
                                        name = sp.get('name') or sp.get(
                                            'nombre') or ''
                                        degree = sp.get('degree') or sp.get(
                                            'grado') or ''
                                        org = sp.get('organization') or sp.get(
                                            'organizacion') or sp.get('institucion') or ''
                                        _append_speaker(name, degree, org)
                                entries = []
                            else:
                                entries = [str(parsed)]
                        except Exception:
                            entries = []

                    # Now parse each entry by '|'. If after splitting there are unexpected
                    # concatenations due to commas inside names (e.g. "Name,Dr."), try to
                    # recover common patterns where a comma is followed by a degree.
                    common_degree_suffixes = (
                        'Ing.', 'MIA.', 'Dr.', 'Dra.', 'Mtro.', 'Lic.', 'Lic', 'Ing')
                    for ent in entries:
                        pieces = [x.strip() for x in ent.split('|')]
                        # If pieces count is 1 but contains multiple '|' in text, try again
                        if len(pieces) == 1 and '|' in ent:
                            pieces = [x.strip() for x in ent.split('|')]

                        if len(pieces) == 3:
                            degree, name, org = pieces
                            # If the 'name' contains a comma and then a degree-like token
                            # it likely means multiple speakers were comma-separated and
                            # the fallback split by ',' merged them. Try to split by comma
                            # and detect the degree token.
                            if ',' in name:
                                subparts = [s.strip()
                                            for s in name.split(',') if s.strip()]
                                # Example: ['Nancy López Arreola', 'Ing.']
                                if len(subparts) == 2 and any(subparts[1].startswith(ds) for ds in common_degree_suffixes):
                                    # First speaker
                                    _append_speaker(subparts[0], degree, org)
                                    # Second speaker uses the subparts[1] as degree and 'org' is likely actually the second name
                                    _append_speaker(org, subparts[1], inst_val)
                                    continue
                            _append_speaker(name, degree, org)
                        elif len(pieces) == 2:
                            degree, name = pieces
                            # if name contains comma+degree, split similarly
                            if ',' in name:
                                subparts = [s.strip()
                                            for s in name.split(',') if s.strip()]
                                if len(subparts) == 2 and any(subparts[1].startswith(ds) for ds in common_degree_suffixes):
                                    _append_speaker(
                                        subparts[0], degree, inst_val)
                                    _append_speaker(subparts[1], '', inst_val)
                                    continue
                            _append_speaker(name, degree, inst_val)
                        else:
                            # Single piece: may contain comma-separated multiple speakers (e.g. "Name1,Title1,Name2,Title2")
                            if ',' in pieces[0]:
                                parts_by_comma = [
                                    s.strip() for s in pieces[0].split(',') if s.strip()]
                                # Try to pair them: degree/name or name/degree patterns
                                i = 0
                                while i < len(parts_by_comma):
                                    a = parts_by_comma[i]
                                    b = parts_by_comma[i+1] if i + \
                                        1 < len(parts_by_comma) else None
                                    if b and any(b.startswith(ds) for ds in common_degree_suffixes):
                                        # a is name, b is degree
                                        _append_speaker(a, b, inst_val)
                                        i += 2
                                    else:
                                        # treat as name with no degree
                                        _append_speaker(a, '', inst_val)
                                        i += 1
                            else:
                                _append_speaker(pieces[0], '', inst_val)

            activity_data['speakers'] = speakers

            # Target audience
            tg = rowdict.get('target_general')
            careers = rowdict.get('target_careers')
            target = {'general': False, 'careers': []}
            if tg is not None and (str(tg).strip().lower() in ('1', 'true', 'yes', 'y', 'si', 's', 'sí')):
                target['general'] = True
            if careers:
                if isinstance(careers, str):
                    target['careers'] = [c.strip()
                                         for c in careers.split(',') if c.strip()]
                else:
                    try:
                        target['careers'] = list(careers)
                    except Exception:
                        target['careers'] = []

            activity_data['target_audience'] = target

            max_val = rowdict.get('max_capacity')
            if max_val not in (None, ''):
                try:
                    activity_data['max_capacity'] = int(float(str(max_val)))
                except Exception:
                    activity_data['max_capacity'] = None

            # Validate with schema (will raise ValidationError)
            from app.schemas import activity_schema as _schema
            loaded = _schema.load(activity_data)

            parsed_rows.append({'row': idx, 'data': loaded})

        except Exception as e:
            # Include raw composed value if available to help debugging formats
            extra = {}
            try:
                if 'composed_val' in locals() and composed_val is not None:
                    extra['composed_raw'] = str(composed_val)
            except Exception:
                pass
            errdata = rowdict if 'rowdict' in locals() else {}
            errdata.update(extra)
            errors.append({'row': idx, 'message': str(e), 'data': errdata})

    # Helper to produce a serializable preview of loaded data
    def _serialize_preview(d):
        out = {}
        if not isinstance(d, dict):
            try:
                out = dict(d)
            except Exception:
                return {}

        for k, v in list(out.items()):
            # Datetime objects -> ISO strings
            try:
                if hasattr(v, 'isoformat') and callable(v.isoformat):
                    iso = safe_iso(v)
                    out[k] = iso if iso is not None else v
                    continue
            except Exception:
                pass

            # JSON-like fields (speakers, target_audience) ensure serializable
            if k in ('speakers', 'target_audience'):
                try:
                    out[k] = json.loads(json.dumps(v, default=str))
                except Exception:
                    out[k] = v
                continue

            # Fallback: simple types or str()
            try:
                json.dumps(v)
                out[k] = v
            except Exception:
                out[k] = str(v)

        # Provide a compact preview with common fields for the UI
        preview = {
            'name': out.get('name'),
            'department': out.get('department'),
            'start_datetime': out.get('start_datetime'),
            'end_datetime': out.get('end_datetime'),
            'activity_type': out.get('activity_type'),
        }
        return preview

    # If dry_run, return validation result without committing with a richer report
    if dry_run:
        total_rows = int(df.shape[0])
        valid = len(parsed_rows)
        invalid = len(errors)

        # Build combined per-row report (keep order by row)
        rows_report = []
        for pr in parsed_rows:
            rows_report.append({
                'row': pr['row'],
                'status': 'ok',
                'message': None,
                'data': _serialize_preview(pr['data'])
            })

        for err in errors:
            rows_report.append({
                'row': err.get('row', None),
                'status': 'error',
                'message': err.get('message'),
                'data': err.get('data', {})
            })

        rows_report = sorted(rows_report, key=lambda x: (
            x['row'] if x['row'] is not None else 999999))

        report = {
            'created': 0,
            'summary': {
                'total_rows': total_rows,
                'valid': valid,
                'invalid': invalid
            },
            'rows': rows_report,
            'errors': errors
        }

        return report

    # Otherwise create activities row-by-row (each its own transaction) and skip duplicates
    created_ids = []
    for pr in parsed_rows:
        data = pr['data']
        # Ensure event id present
        if not data.get('event_id') and event_id:
            data['event_id'] = int(event_id)

        # Duplicate detection: event_id + name + start_datetime
        try:
            q = Activity.query.filter_by(
                event_id=data.get('event_id'), name=data.get('name'))
            existing = None
            if data.get('start_datetime') is not None:
                existing = q.filter(Activity.start_datetime ==
                                    data.get('start_datetime')).first()
            else:
                existing = q.first()

            if existing:
                errors.append(
                    {'row': pr['row'], 'message': 'Duplicada: actividad ya existe (omitir)', 'data': data})
                continue
        except Exception:
            # If duplicate detection failed, continue and let creation attempt detect violations
            pass

        try:
            activity = create_activity(data)
            created += 1
            created_ids.append(activity.id)
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            errors.append({'row': pr['row'], 'message': str(e), 'data': data})

    return {'created': created, 'errors': errors, 'created_ids': created_ids}
