"""MindCare: AI-Based Mental Health Risk Screening and Support System."""
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, render_template
from markupsafe import Markup, escape

BASE_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "MindCare"
APP_TITLE = "AI-Based Mental Health Risk Screening and Support System"


def _load_or_create_secret(instance_path: str) -> str:
    path = Path(instance_path) / "secret_key"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_hex(32)
    path.write_text(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def create_app(test_config=None):
    app = Flask(__name__, instance_path=str(BASE_DIR / "instance"))
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or _load_or_create_secret(app.instance_path),
        DATABASE=os.path.join(app.instance_path, "mindcare.sqlite3"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    from . import auth, db, resources, screening, security, views

    db.init_app(app)
    security.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(screening.bp)
    app.register_blueprint(views.bp)

    app.jinja_env.globals.update(
        app_name=APP_NAME, app_title=APP_TITLE, helplines=resources.HELPLINES, emergency=resources.EMERGENCY
    )

    @app.template_filter("dt")
    def dt_filter(value, fmt="%d %b %Y, %H:%M"):
        """Render a UTC ISO timestamp; app.js converts it to the viewer's local time."""
        if not value:
            return ""
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return escape(value)
        return Markup('<time class="js-local" datetime="{}">{} UTC</time>').format(value, parsed.strftime(fmt))

    @app.template_filter("dateonly")
    def dateonly_filter(value):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d %b %Y")
        except (ValueError, TypeError):
            return value

    def _error(code, title, message):
        return render_template("error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(e):
        return _error(400, "Request could not be completed", getattr(e, "description", "Bad request."))

    @app.errorhandler(404)
    def not_found(e):
        return _error(404, "Page not found", "The page you are looking for does not exist or is not available to you.")

    @app.errorhandler(413)
    def too_large(e):
        return _error(413, "Message too long", "That submission was too large. Please shorten it and try again.")

    @app.errorhandler(500)
    def server_error(e):
        return _error(500, "Something went wrong", "An unexpected error occurred. Please try again in a moment.")

    return app
