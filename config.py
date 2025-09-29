import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get(
        'SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Build the SQLALCHEMY_DATABASE_URI in a robust way:
    # - Prefer DATABASE_URL if provided (full URI)
    # - Otherwise compose from DB_USER, DB_PASSWORD, DB_HOST, DB_PORT and DB_NAME
    # URL-encode user and password to avoid issues with special characters
    _database_url = os.environ.get('DATABASE_URL')
    if _database_url:
        SQLALCHEMY_DATABASE_URI = _database_url
    else:
        DB_USER = os.environ.get('DB_USER', 'root')
        DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
        DB_HOST = os.environ.get('DB_HOST', 'localhost')
        DB_PORT = os.environ.get('DB_PORT', '')
        DB_NAME = os.environ.get('DB_NAME', 'eventos_tec')

        host = f"{DB_HOST}:{DB_PORT}" if DB_PORT else DB_HOST
        user_q = quote_plus(DB_USER)
        pw_q = quote_plus(DB_PASSWORD)
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{user_q}:{pw_q}@{host}/{DB_NAME}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get(
        'JWT_SECRET_KEY') or 'jwt-secret-string-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hora
    # Asegurar que busca el token en los headers
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    # Usar base de datos sqlite en disco para tests para evitar problemas de conexiones
    SQLALCHEMY_DATABASE_URI = 'sqlite:///test_eventostec.db'
    WTF_CSRF_ENABLED = False  # Deshabilitar CSRF para tests


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,      # Agregado
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
