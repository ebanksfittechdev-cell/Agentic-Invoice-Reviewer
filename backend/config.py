import os

DEFAULT_DATABASE_URL = "sqlite:///invoice_reviewer.db"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "/tmp/invoice_uploads")
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = FLASK_ENV == "production"
