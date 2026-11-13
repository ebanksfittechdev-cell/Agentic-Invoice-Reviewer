import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    CORS(app, origins=["http://localhost:5173"], supports_credentials=True)

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
