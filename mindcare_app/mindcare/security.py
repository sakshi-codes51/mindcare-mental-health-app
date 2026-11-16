"""Session loading, CSRF protection, login guard and security headers."""
import functools
import hmac
import secrets

from flask import abort, flash, g, redirect, request, session, url_for

from .db import get_db

CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data:; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def csrf_token() -> str:
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def safe_next(target: str):
    """Only allow same-site relative redirects."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return None


def init_app(app):
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def load_user():
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            row = get_db().execute(
                "SELECT id, name, email, user_type, age_group, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                session.clear()
            else:
                g.user = row

    @app.before_request
    def csrf_protect():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token") or ""
            expected = session.get("_csrf", "")
            if not expected or not hmac.compare_digest(sent, expected):
                abort(400, description="Your session expired or the form was invalid. Please refresh the page and try again.")

    @app.after_request
    def set_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Content-Security-Policy", CSP)
        if request.endpoint != "static":
            resp.headers["Cache-Control"] = "no-store"
        return resp
