import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get(
        'SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f"mysql+pymysql://{os.environ.get('DB_USER', 'root')}:{os.environ.get('DB_PASSWORD', '')}@{os.environ.get('DB_HOST', 'localhost')}/{os.environ.get('DB_NAME', 'eventos_tec')}"
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
