from app.schemas.event_schema import event_schema, events_schema
from app.schemas.activity_schema import activity_schema, activities_schema
from app.schemas.student_schema import student_schema, students_schema
from app.schemas.user_schema import user_schema, users_schema, user_login_schema  # Agregado
from app.schemas.attendance_schema import attendance_schema, attendances_schema
from app.schemas.registration_schema import registration_schema, registrations_schema

__all__ = [
    'event_schema', 'events_schema',
    'activity_schema', 'activities_schema',
    'student_schema', 'students_schema',
    'user_schema', 'users_schema', 'user_login_schema',
    'attendance_schema', 'attendances_schema',
    'registration_schema', 'registrations_schema'
]
