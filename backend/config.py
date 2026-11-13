import os


def _sqlalchemy_url(raw: str | None) -> str | None:
    """Ensure the DATABASE_URL uses the psycopg2 driver prefix for SQLAlchemy 2."""
    if not raw:
        return raw
    # Replace plain 'postgresql://' or 'postgres://' with the explicit psycopg2 dialect
    if raw.startswith("postgres://"):
        raw = "postgresql+psycopg2://" + raw[len("postgres://"):]
    elif raw.startswith("postgresql://") and "+psycopg" not in raw:
        raw = "postgresql+psycopg2://" + raw[len("postgresql://"):]
    return raw


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DATABASE_URL = _sqlalchemy_url(os.environ.get("DATABASE_URL"))
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "/tmp/invoice_uploads")
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = FLASK_ENV == "production"
