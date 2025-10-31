# Student Hours Tracking by Event - Feature Documentation

## Overview

This feature implements a comprehensive system for tracking student participation hours by event, including badge indicators for complementary credits when students accumulate 10+ hours in a single event.

## Components Implemented

### Backend (Python/Flask)

#### New Endpoints in `/api/students`:

1. **GET `/api/students/`** (Enhanced)
   - Added filters: `event_id`, `activity_id`, `career`
   - Supports searching by control number or name
   - Returns paginated list of students filtered by participation

2. **GET `/api/students/<student_id>/hours-by-event`**
   - Returns student's hours grouped by event
   - Only counts registrations with status='Asistió'
   - Includes `has_complementary_credit` flag (true when hours >= 10)
   - Response structure:
     ```json
     {
       "student": {...},
       "events_hours": [
         {
           "event_id": 1,
           "event_name": "Event Name",
           "total_hours": 12.5,
           "activities_count": 3,
           "has_complementary_credit": true
         }
       ]
     }
     ```

3. **GET `/api/students/<student_id>/event/<event_id>/details`**
   - Returns chronological list of activities for a specific event
   - Includes registration status and confirmation dates
   - Shows total confirmed hours and complementary credit status

### Frontend - Admin Section

#### Files Created:

- `app/static/js/admin/students.js` - Alpine.js component
- `app/templates/admin/partials/students.html` - Template
- `app/static/js/admin/__tests__/students.test.js` - Unit tests

#### Features:

- **Student List View**:
  - Search by control number or name
  - Filter by event, activity, and career
  - Responsive table/card layout
  - Pagination support

- **Student Detail Modal**:
  - Shows all events with confirmed hours
  - Displays complementary credit badge for events with 10+ hours
  - Lists total hours and activity count per event

- **Event Activity Timeline Modal**:
  - Chronological view of student's participation
  - Shows status of each activity (Asistió, Confirmado, etc.)
  - Visual timeline with status icons

### Frontend - Student Section

#### Files Created:

- `app/static/js/student/history.js` - Alpine.js component
- `app/templates/student/partials/history.html` - Template
- `app/static/js/student/__tests__/history.test.js` - Unit tests

#### Features:

- **History Table View**:
  - Lists all events with confirmed hours
  - Shows total hours and activity count
  - Complementary credit badge when applicable
  - Responsive design for mobile/desktop

- **Event Detail Modal**:
  - Timeline view of activities with status
  - Shows confirmed hours and credit status
  - Includes activity details (type, location, dates)

### Tests

#### Backend Tests (`app/tests/api/test_students_hours.py`):

- ✓ Filter students by event/activity
- ✓ Calculate hours by event
- ✓ Generate event activity details
- ✓ Only count 'Asistió' status toward hours
- ✓ Complementary credit badge logic (>=10 hours)
- ✓ Error handling for non-existent resources

#### Frontend Tests:

- ✓ Admin students component initialization and CRUD
- ✓ Student history component initialization and data loading
- ✓ Status badge class mapping
- ✓ Error handling

## Business Logic

### Hours Calculation

- Only registrations with `status='Asistió'` count toward total hours
- Hours are summed using the `duration_hours` field from activities
- Each event's hours are calculated independently

### Complementary Credit

- Badge shows when `total_hours >= 10.0` for an event
- Displayed as green badge with award icon
- Label: "Crédito Complementario" (admin) / "Acreditado" (student)

## UI/UX Features

### Admin Dashboard

- New "Estudiantes" menu item
- Advanced filtering interface
- Two-level detail view (event list → activity timeline)
- Clear visual indicators for credit status

### Student Dashboard

- New "Histórico de Horas" menu item
- Easy-to-read table showing participation summary
- Quick access to detailed activity chronology
- Informational callout explaining credit requirements

## Integration Points

### With Existing Code:

- Uses existing registration and activity models
- Leverages existing authentication system
- Follows established Alpine.js patterns
- Consistent with existing UI/UX design

### Database:

- No schema changes required
- Uses existing tables: `students`, `events`, `activities`, `registrations`
- Efficient queries with joins and grouping

## Usage Examples

### Admin: Finding students in an event

1. Navigate to "Estudiantes" tab
2. Select event from dropdown
3. Click "Aplicar Filtros"
4. Click "Ver Detalle" on any student to see hours breakdown

### Student: Checking hours and credit status

1. Navigate to "Histórico de Horas" tab
2. View table with all events and confirmed hours
3. Green "Acreditado" badge indicates 10+ hours earned
4. Click "Ver Detalle" to see activity-by-activity breakdown

## Notes

- The feature is read-only for students (view participation history only)
- Admin view allows filtering and detailed analysis
- All hour calculations are performed on the backend for data integrity
- Frontend displays are responsive and mobile-friendly
