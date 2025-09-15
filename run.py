from app import create_app
import os

app = create_app(os.getenv('FLASK_CONFIG') or 'default')

if __name__ == '__main__':
    # En Windows algunas configuraciones (antivirus, políticas locales o el reloader)
    # pueden causar PermissionError: [WinError 10013] al abrir sockets.
    # Forzamos bind a localhost y desactivamos el reloader para evitar ese problema
    # cuando se ejecuta directamente con `python run.py` desde VS Code.
    app.run(host='127.0.0.1', port=5001, debug=True, use_reloader=False)
