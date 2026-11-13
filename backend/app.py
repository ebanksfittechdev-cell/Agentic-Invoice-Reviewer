import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()


def create_app(config_overrides: dict | None = None):
    app = Flask(__name__)
    app.config.from_object("config.Config")

    # SQLAlchemy needs the URI under this key
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Apply test/override config BEFORE db.init_app() so the engine is built
    # against the correct URI (e.g. sqlite:///:memory: in tests).
    app.config.update(config_overrides or {})

    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if uri.startswith(("postgres://", "postgresql://", "postgresql+")):
        raise RuntimeError(
            "PostgreSQL support has been removed. Set DATABASE_URL to "
            "'sqlite:///invoice_reviewer.db' in backend/.env."
        )

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from db import db
    db.init_app(app)

    default_origins = "http://localhost:5173,http://127.0.0.1:5173"
    origins = [o.strip() for o in os.environ.get("FRONTEND_ORIGINS", default_origins).split(",") if o.strip()]
    CORS(app, origins=origins, supports_credentials=True)

    from auth.routes import auth_bp
    from invoices.routes import invoices_bp
    from actions.routes import actions_bp
    from history.routes import history_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(invoices_bp, url_prefix="/api/invoices")
    app.register_blueprint(actions_bp, url_prefix="/api/actions")
    app.register_blueprint(history_bp, url_prefix="/api/history")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
