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

## Future Improvements
Consider migrating to MySQL TIMESTAMP columns (stores UTC) or always storing timezone-aware datetimes to avoid this ambiguity.
