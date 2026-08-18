import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "pos-super-secret-key-change-in-production-v6.0")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-pos-secret-key-change-in-production-v6.0")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # SQLAlchemy configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'pos_v6.sqlite3'}"
    )
    
    # Licensing keys paths
    KEYS_DIR = BASE_DIR / "keys"
    ED25519_PRIVATE_KEY_PATH = os.environ.get("ED25519_PRIVATE_KEY_PATH", str(KEYS_DIR / "license_private_ed25519.pem"))
    ED25519_PUBLIC_KEY_PATH = os.environ.get("ED25519_PUBLIC_KEY_PATH", str(KEYS_DIR / "license_public_ed25519.pem"))
    
    # CORS
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}
