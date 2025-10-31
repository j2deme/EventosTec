# script_create_admin.py (archivo temporal para crear admin)
from app import create_app, db
from app.models.user import User

app = create_app()

with app.app_context():
    # Verificar si ya existe
    existing_admin = User.query.filter_by(username="admin").first()
    if existing_admin:
        print("Usuario admin ya existe")
    else:
        # Crear usuario administrador
        admin = User(
            username="admin",
            email="admin@tecvalles.mx",
            role="Admin",  # Asegúrate de que coincida con tu enum
        )
        admin.set_password("admin123")  # Contraseña de prueba
        db.session.add(admin)
        db.session.commit()
        print("Usuario admin creado exitosamente")
        print("Usuario: admin")
        print("Contraseña: admin123")
