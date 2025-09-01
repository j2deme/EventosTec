# Eventos Tec

Sistema de control de asistencias para institución educativa.

## Instalación

1. Crear entorno virtual:

   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # o
   venv\Scripts\activate     # Windows
   ```

2. Instalar dependencias:

   ```bash
   pip install -r requirements.txt
   ```

3. Configurar variables de entorno:

   ```bash
   cp .env.example .env
   ```

4. Inicializar la base de datos:

   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

5. Ejecutar:

   ```bash
   flask run # python run.py
   ```

## Estructura

- `app/` - Aplicación principal
- `app/models/` - Modelos de datos
- `app/api/` - Endpoints de la API
- `app/services/` - Lógica de negocio
- `app/utils/` - Utilidades y helpers
