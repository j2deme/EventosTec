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

## Usage Workflow

1. Admin navigates to "Estudiantes" section
2. Clicks "Exportar Créditos" button (green)
3. Modal opens
4. Selects an event from dropdown (required)
5. Optionally enters career name to filter
6. Clicks "Buscar Estudiantes"
7. Reviews the list in the preview table
8. Clicks "Descargar Excel" to download the file
9. Excel file downloads with formatted data ready for institutional processing

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
