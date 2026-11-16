"""Module 1: registration, login/logout, profile management."""
import re
import sqlite3
import time

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, utcnow
from .security import login_required, safe_next

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USER_TYPES = [
    ("student", "College / university student"),
    ("professional", "Working professional"),
    ("other", "Other / prefer not to say"),
]
AGE_GROUPS = ["18-24", "25-34", "35-44", "45-54", "55+"]
COMMON_PASSWORDS = {"password1", "password123", "12345678a", "qwerty123", "iloveyou1", "welcome123"}

MAX_FAILS = 5
LOCK_WINDOW_SECONDS = 15 * 60
# Used to keep response time similar whether or not the email exists.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def _password_error(password: str, email: str = ""):
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if len(password) > 128:
        return "Password must be 128 characters or fewer."
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "Password must include both letters and numbers."
    if password.lower() in COMMON_PASSWORDS or (email and password.lower() == email.lower()):
        return "That password is too easy to guess. Please choose another."
    return None


def _start_session(user_id: int):
    session.clear()
    session["user_id"] = user_id
    session.permanent = True


def _clean_name(raw: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", "", raw or "")).strip()


def _valid_choice(value, allowed):
    return value if value in allowed else None


@bp.route("/register", methods=("GET", "POST"))
def register():
    if g.user:
        return redirect(url_for("views.dashboard"))
    form = {}
    errors = []
    if request.method == "POST":
        form = {
            "name": _clean_name(request.form.get("name")),
            "email": (request.form.get("email") or "").strip().lower(),
            "user_type": request.form.get("user_type", "other"),
            "age_group": request.form.get("age_group", ""),
        }
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not 2 <= len(form["name"]) <= 60:
            errors.append("Please enter your name (2 to 60 characters).")
        if not EMAIL_RE.match(form["email"]) or len(form["email"]) > 254:
            errors.append("Please enter a valid email address.")
        pw_err = _password_error(password, form["email"])
        if pw_err:
            errors.append(pw_err)
        elif password != confirm:
            errors.append("The two passwords do not match.")
        if form["user_type"] not in {t for t, _ in USER_TYPES}:
            form["user_type"] = "other"
        if form["age_group"] not in AGE_GROUPS:
            errors.append("Please choose your age group. This service is for adults aged 18 and over.")
        if request.form.get("adult") != "on":
            errors.append("Please confirm that you are 18 or older.")
        if request.form.get("ack") != "on":
            errors.append("Please confirm that you understand this is a screening tool, not a diagnosis.")

        if not errors:
            db = get_db()
            try:
                cur = db.execute(
                    "INSERT INTO users (name, email, password_hash, user_type, age_group, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (form["name"], form["email"], generate_password_hash(password),
                     form["user_type"], form["age_group"], utcnow()),
                )
                db.commit()
            except sqlite3.IntegrityError:
                errors.append("An account with that email already exists. Try logging in instead.")
            else:
                _start_session(cur.lastrowid)
                flash("Welcome to MindCare! A good first step is the short screening questionnaire.", "success")
                return redirect(url_for("views.dashboard"))
    return render_template("auth/register.html", form=form, errors=errors,
                           user_types=USER_TYPES, age_groups=AGE_GROUPS)


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("views.dashboard"))
    error = None
    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        now = time.time()
        db.execute("DELETE FROM login_attempts WHERE ts < ?", (now - LOCK_WINDOW_SECONDS,))
        fails = db.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE email = ? AND ts > ?",
            (email, now - LOCK_WINDOW_SECONDS),
        ).fetchone()[0]
        if fails >= MAX_FAILS:
            db.commit()
            error = "Too many failed attempts. Please wait about 15 minutes and try again."
        else:
            user = db.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
            ok = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password)
            if user and ok:
                db.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
                db.commit()
                _start_session(user["id"])
                return redirect(safe_next(request.args.get("next", "")) or url_for("views.dashboard"))
            db.execute("INSERT INTO login_attempts (email, ts) VALUES (?, ?)", (email, now))
            db.commit()
            error = "Incorrect email or password."
    return render_template("auth/login.html", error=error, email=email)


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("views.index"))


@bp.route("/profile", methods=("GET", "POST"))
@login_required
def profile():
    errors = []
    if request.method == "POST":
        name = _clean_name(request.form.get("name"))
        user_type = _valid_choice(request.form.get("user_type"), {t for t, _ in USER_TYPES})
        age_group = _valid_choice(request.form.get("age_group"), set(AGE_GROUPS))
        if not 2 <= len(name) <= 60:
            errors.append("Please enter your name (2 to 60 characters).")
        if not user_type or not age_group:
            errors.append("Please choose valid options for role and age group.")
        if not errors:
            db = get_db()
            db.execute("UPDATE users SET name = ?, user_type = ?, age_group = ? WHERE id = ?",
                       (name, user_type, age_group, g.user["id"]))
            db.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html", errors=errors, user_types=USER_TYPES, age_groups=AGE_GROUPS)


@bp.route("/profile/password", methods=("POST",))
@login_required
def change_password():
    db = get_db()
    row = db.execute("SELECT password_hash, email FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    current = request.form.get("current", "")
    new = request.form.get("new", "")
    confirm = request.form.get("confirm", "")
    if not check_password_hash(row["password_hash"], current):
        flash("Your current password was incorrect.", "danger")
    elif _password_error(new, row["email"]):
        flash(_password_error(new, row["email"]), "danger")
    elif new != confirm:
        flash("The new passwords do not match.", "danger")
    else:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new), g.user["id"]))
        db.commit()
        flash("Password changed.", "success")
    return redirect(url_for("auth.profile"))


@bp.route("/profile/delete", methods=("POST",))
@login_required
def delete_account():
    db = get_db()
    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    if not check_password_hash(row["password_hash"], request.form.get("password", "")):
        flash("Password incorrect. Your account was not deleted.", "danger")
        return redirect(url_for("auth.profile"))
    db.execute("DELETE FROM users WHERE id = ?", (g.user["id"],))
    db.commit()
    session.clear()
    flash("Your account and all of its data have been permanently deleted.", "info")
    return redirect(url_for("views.index"))
