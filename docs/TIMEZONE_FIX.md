# Timezone Handling Fix Documentation

## Problem

The public pause-attendance view was showing error messages like "La ventana pública de control ha expirado" (The public control window has expired) even during ongoing activities.

## Root Cause

The database stores datetime values as **naive** (no timezone information) in MySQL DATETIME columns. When the application reads these values back:

1. Frontend sends: `2025-01-06T15:00:00-06:00` (3 PM Mexico City time)
2. SQLAlchemy stores: `15:00` (naive, loses the `-06:00` offset)
3. Code reads back: `15:00` (naive)
4. **Old behavior**: Treats `15:00` as UTC → wrong! It's actually local time
5. Comparison: `now (21:00 UTC)` > `end (15:00 treated as UTC)` → "expired"
6. **Reality**: It's 3 PM local, activity is ongoing!

The 6-hour mismatch (Mexico City is UTC-6) caused activities to appear expired when they were actually ongoing.

## Solution

### 1. Added `APP_TIMEZONE` Configuration

```python
# config.py
APP_TIMEZONE = os.environ.get('APP_TIMEZONE', 'America/Mexico_City')
```

### 2. Created `localize_naive_datetime()` Utility

```python
# app/utils/datetime_utils.py
def localize_naive_datetime(dt, app_timezone='America/Mexico_City'):
    """
    Localizes a naive datetime to the app timezone and converts to UTC.

    - If dt already has timezone, converts to UTC
    - If dt is naive, assumes it's in app_timezone and converts to UTC
    """
```

### 3. Updated All Public Pause/Resume Endpoints

Modified these endpoints to use `localize_naive_datetime()`:

- `GET /public/pause-attendance/<token>`
- `GET /api/public/attendances/search`
- `POST /api/public/attendances/<int:attendance_id>/pause`
- `POST /api/public/attendances/<int:attendance_id>/resume`

## Impact

✅ Public pause view now correctly identifies ongoing activities
✅ No more false "expired" messages during events
✅ Timezone-aware comparisons work correctly
✅ Supports both `zoneinfo` (Python 3.9+) and `pytz` (fallback)

## Testing

Added comprehensive tests in `app/tests/api/test_public_pause_attendance_timezone.py`:

- Tests for ongoing activities (should be accessible)
- Tests for expired activities (should show expired message)
- Tests for recent activities (within grace period)
- API endpoint tests (search, pause, resume)

## Configuration

Set in `.env` file:

```bash
APP_TIMEZONE=America/Mexico_City
```

## Migration Notes

No database migration required. The fix handles existing naive datetime data correctly by interpreting it as being in the configured timezone.

## Write-Side Alignment: Attendance Timestamps (2026-10-06)

The read side was fixed (naive = local). The **write** side was not: several paths persisted `datetime.now(timezone.utc)` or `db.func.now()` (the MySQL server runs UTC), so the column held a **UTC** wall time that was later read as local — a 6-hour shift in the opposite direction.

### Evidence

- `EventosTec-2026-10-02-04-33-53.sql`: `check_in_time == created_at` in 400/400 rows, and the 64 check-ins for the magistral starting at 10:00 local were recorded between 15:19 and 15:54 (UTC wall).
- Effect: `activities.start_datetime` is local wall while `attendances.check_in_time` was UTC wall. Read as local, `check_in` lands _after_ `start`, the presence window comes out inverted and `calculate_attendance_percentage()` returns **0%**.
- Why it was never noticed: `batch-checkout` (added 2026-09-28) had never run on real data. The 46° Aniversario (2026-10-05 → 10-09) would have been batch-closed at 0%.

### Fix

Server-generated instants are persisted through a helper that stores **local wall time**, the same convention used by activities and by client payloads:

```python
# app/utils/datetime_utils.py
def db_wall_local(dt, app_timezone=None):
    """naive → already local (unchanged); aware → APP_TIMEZONE, drop tzinfo."""


def db_now_local(app_timezone=None):
    """datetime.now() ready to persist (naive local wall time)."""
    return db_wall_local(datetime.now(timezone.utc), app_timezone)
```

Write sites converted:

| File                                 | What                                                                              |
| ------------------------------------ | --------------------------------------------------------------------------------- |
| `app/api/attendances_bp.py`          | check-in/out fallbacks (`now`) and `att.check_out_time = now` in `batch-checkout` |
| `app/api/registrations_bp.py`        | 8 × `db.func.now()` (bulk check-in/out)                                           |
| `app/api/public_registrations_bp.py` | walk-in and confirmation `check_in_time`                                          |
| `app/api/self_register_bp.py`        | self check-in `check_in_time`                                                     |
| `app/services/attendance_service.py` | `pause_attendance()` → `pause_time`                                               |

**Payload values are not converted.** `parse_datetime_with_timezone()` keeps the wall time the client sent (an `<input type="datetime-local">` value is naive local and is deliberately tagged as UTC), so wrapping it in `db_wall_local()` would subtract 6 hours from every manual check-in. Comparisons keep using aware UTC (`datetime.now(timezone.utc)`); only _assignments_ are converted.

### Migration notes

- No schema or data migration. Rows written before 2026-10-06 still hold UTC wall time and keep reading 6 h off; past events are closed and are not recalculated.
- Side effect: the admin check-in column now shows the real arrival time instead of +6 h.
- Tests: `tests/test_datetime_utils_wall_local.py` (write → read round trip), plus the existing suites.

## Future Improvements

Consider migrating to MySQL TIMESTAMP columns (stores UTC) or always storing timezone-aware datetimes to avoid this ambiguity.
