# Export Complementary Credits Feature

## Overview

This feature adds the ability to filter and export students who have earned complementary credits (10+ hours) in a specific event, with optional filtering by career.

## User Interface

### Export Button

A new green "Exportar Créditos" button has been added to the students section header, next to the existing filter buttons.

### Export Modal

When clicked, a modal opens with:

1. **Filter Section**
   - Event selector (required) - dropdown with all events
   - Career filter (optional) - text input for filtering by career name

2. **Search Button**
   - "Buscar Estudiantes" button to load matching students
   - Shows loading state while fetching data

3. **Results Preview**
   - Table showing:
     - Number (sequential)
     - Control Number
     - Full Name
     - Career
     - Confirmed Hours (badge with green background)
     - Activity Count
   - Total count of students found
   - "Descargar Excel" button to export the data

4. **Empty State**
   - Message when no students meet the criteria
   - Clear indication that filters can be adjusted

## Backend Implementation

### New Endpoints

#### GET `/api/students/complementary-credits`

**Purpose**: Returns students with 10+ confirmed hours for a specific event

**Query Parameters**:

- `event_id` (required): ID of the event
- `career` (optional): Filter by career name (partial match)

**Response**:

```json
{
  "event": {
    "id": 1,
    "name": "Event Name",
    "start_date": "2024-01-01T00:00:00",
    "end_date": "2024-01-07T23:59:59"
  },
  "students": [
    {
      "id": 1,
      "control_number": "12345678",
      "full_name": "John Doe",
      "career": "Computer Engineering",
      "email": "john@example.com",
      "total_hours": 12.5,
      "activities_count": 3,
      "has_complementary_credit": true
    }
  ],
  "total_students": 1
}
```

#### GET `/api/students/complementary-credits/export`

**Purpose**: Exports the filtered students to an Excel file

**Query Parameters**: Same as above

**Response**: Excel file (.xlsx) download

**Excel Format**:

- Title row with event name
- Generation timestamp
- Optional career filter indication
- Header row with column names
- Data rows with student information
- Summary row with total count
- Styled headers (blue background, white text)
- Auto-adjusted column widths

## Features

✅ **Filter by Event**: Required - shows only students who participated in that event
✅ **Filter by Career**: Optional - narrows results to specific career programs
✅ **Preview Results**: See the list before downloading
✅ **Excel Export**: Professional formatted spreadsheet for institutional use
✅ **10+ Hours Only**: Automatically filters to students with complementary credit
✅ **Real-time Validation**: Ensures event is selected before searching
✅ **Responsive Modal**: Works on desktop and mobile devices
✅ **Multi-event accumulation**: Hours add up across every selected event
✅ **Grant tracking**: Recording a grant marks its events as consumed so the
student cannot be exported twice (see _Credit granting_ below)

## Usage Workflow

1. Admin navigates to "Estudiantes" section
2. Clicks "Exportar Créditos" button (green)
3. Modal opens
4. Selects an event from dropdown (required)
5. Optionally enters career name to filter
6. Clicks "Buscar Estudiantes"
7. Reviews the list in the preview table (students already granted credit are
   excluded; tick **Ver ya otorgados** to see them marked, for auditing only)
8. Chooses one of:
   - **Otorgar crédito (N)**: confirms the prompt, downloads the XLSX of the
     pending students and records the grant in `credit_grants`.
   - **Descargar sin otorgar**: downloads the XLSX without recording anything.
9. Excel file downloads with formatted data ready for institutional processing

## Credit granting (credit_grants)

The XLSX is uploaded by hand to the external platform, so downloading the same
list twice would credit the same student twice. `credit_grants` prevents that:

- A **grant** stores one row per `student + event` that was _consumed_: every
  event that contributed **unspent** hours from the start up to the moment the
  10 h threshold was crossed. Events after the crossing stay untouched and can
  feed a **second** credit later.
- On the next search those events are removed from the calculation, so the
  student only reappears when they accumulate 10 **fresh** hours in other
  events. The response reports them in `excluded_already_granted`.
- The Excel **never** includes an already-granted student (its summary row
  says how many were omitted). The `include_granted=1` flag only exists on the
  list endpoint, for on-screen auditing.
- Order of operations in the UI: download first, record afterwards. If the
  recording fails, nothing was consumed and retrying is safe.

Endpoints: `POST /api/students/credit-grants` (requires `confirm: true`) and
`GET /api/students/credit-grants` (history grouped by batch).

## Technical Details

- **Authorization**: Requires admin JWT token
- **Performance**: Uses SQL aggregation for efficient queries
- **File Format**: XLSX (Excel 2007+)
- **Styling**: Professional formatting with colors and alignment
- **Error Handling**: Clear messages for invalid requests
- **Validation**: Frontend and backend validation for required fields

## Use Cases

1. **End of Event**: Export list for complementary credit issuance
2. **Audit**: Review which students qualified in specific events
3. **Career Analysis**: See complementary credit distribution by program
4. **Reporting**: Generate institutional reports on student participation
