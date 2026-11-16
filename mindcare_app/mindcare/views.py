"""Main application routes: dashboard, journal, emotion analysis, chat, wellbeing, music, help."""
import json
from datetime import date, datetime, timedelta, timezone

from flask import (Blueprint, abort, flash, g, jsonify, redirect, render_template, request,
                   session, url_for)

from . import analytics, chatbot, resources, wellbeing
from .db import get_db, utcnow
from .emotion import analyze
from .security import login_required

bp = Blueprint("views", __name__)

MOOD_LABELS = {1: "Very low", 2: "Low", 3: "Okay", 4: "Good", 5: "Great"}
MOOD_EMOJI = {1: "\U0001F61E", 2: "\U0001F615", 3: "\U0001F610", 4: "\U0001F642", 5: "\U0001F604"}
EMOTION_EMOJI = {"joy": "\U0001F60A", "calm": "\U0001F60C", "sadness": "\U0001F622", "anxiety": "\U0001F630",
                 "anger": "\U0001F620", "stress": "\U0001F623", "loneliness": "\U0001F614", "neutral": "\U0001F610"}
JOURNAL_PROMPTS = [
    "What is one thing that took up a lot of your energy today?",
    "What are you grateful for right now, however small?",
    "What is something you are worried about, and what part of it can you influence?",
    "Describe a moment today when you felt even a little at ease.",
    "What would you say to a friend who felt the way you do today?",
    "What is one small thing you could do tomorrow to look after yourself?",
    "Who made you feel supported recently, and how?",
]
CHAT_ACTIONS = {
    "breathing": ("Guided breathing", "views.wellbeing_page", {"_anchor": "breathing"}),
    "wellbeing": ("My wellbeing plan", "views.wellbeing_page", {}),
    "journal": ("Open journal", "views.journal", {}),
    "music": ("Music for my mood", "views.music", {}),
    "help": ("Professional help and helplines", "views.help_page", {}),
    "screening": ("Take the screening", "screening.take", {}),
}


@bp.app_context_processor
def inject_helpers():
    return {"mood_emoji": MOOD_EMOJI, "mood_labels": MOOD_LABELS, "emotion_emoji": EMOTION_EMOJI}


def _bounded_int(raw, lo, hi):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if lo <= value <= hi else None


def _bounded_float(raw, lo, hi):
    if raw in (None, ""):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return round(value, 1) if lo <= value <= hi else None


def _today() -> date:
    return datetime.now(timezone.utc).date()


# ------------------------------------------------------------------ public pages
@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/help")
def help_page():
    return render_template("help.html", r=resources)


# ---------------------------------------------------------------------- dashboard
@bp.route("/dashboard")
@login_required
def dashboard():
    uid = g.user["id"]
    chart_data = {
        "mood": analytics.mood_series(uid, 30),
        "emotions": analytics.emotion_distribution(uid, 30),
        "screenings": analytics.screening_series(uid),
    }
    prompt = JOURNAL_PROMPTS[_today().toordinal() % len(JOURNAL_PROMPTS)]
    return render_template(
        "dashboard.html", latest=analytics.latest_screening(uid), stats=analytics.summary_stats(uid),
        insights=analytics.insights(uid), chart_data=chart_data, prompt=prompt,
    )


# ------------------------------------------------------------------------ journal
def _crisis_flash():
    flash("It sounds like you may be going through something very painful. You deserve support from a real person "
          "right now. Please see the helplines on the Help page, or call 112 if you are in immediate danger.",
          "crisis")


@bp.route("/journal", methods=("GET", "POST"))
@login_required
def journal():
    uid = g.user["id"]
    db = get_db()
    errors = []
    if request.method == "POST":
        mood = _bounded_int(request.form.get("mood"), 1, 5)
        stress = _bounded_int(request.form.get("stress"), 1, 5) if request.form.get("stress") else None
        sleep = _bounded_float(request.form.get("sleep_hours"), 0, 24)
        note = (request.form.get("note") or "").strip()
        raw_date = request.form.get("entry_date") or _today().isoformat()
        try:
            entry_date = date.fromisoformat(raw_date)
        except ValueError:
            entry_date = None

        if mood is None:
            errors.append("Please choose how you are feeling (1 to 5).")
        if request.form.get("sleep_hours") and sleep is None:
            errors.append("Sleep hours must be a number between 0 and 24.")
        if len(note) > 2000:
            errors.append("Please keep your note under 2000 characters.")
        if entry_date is None or entry_date > _today() + timedelta(days=1) or entry_date < _today() - timedelta(days=365):
            errors.append("Please choose a valid date within the last year.")

        if not errors:
            result = analyze(note) if note else None
            db.execute(
                "INSERT INTO mood_entries (user_id, created_at, entry_date, mood, sleep_hours, stress, note,"
                " primary_emotion, sentiment, distress) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (uid, utcnow(), entry_date.isoformat(), mood, sleep, stress, note,
                 result["primary"] if result else None, result["sentiment"] if result else None,
                 result["distress"] if result else None),
            )
            db.commit()
            if result and result["crisis"]:
                _crisis_flash()
            else:
                flash("Check-in saved.", "success")
            return redirect(url_for("views.journal"))

    page = max(1, _bounded_int(request.args.get("page"), 1, 10000) or 1)
    per_page = 10
    total = db.execute("SELECT COUNT(*) FROM mood_entries WHERE user_id = ?", (uid,)).fetchone()[0]
    entries = db.execute(
        "SELECT * FROM mood_entries WHERE user_id = ? ORDER BY entry_date DESC, id DESC LIMIT ? OFFSET ?",
        (uid, per_page, (page - 1) * per_page),
    ).fetchall()
    prompt = JOURNAL_PROMPTS[_today().toordinal() % len(JOURNAL_PROMPTS)]
    return render_template("journal.html", entries=entries, errors=errors, page=page,
                           pages=max(1, -(-total // per_page)), today=_today().isoformat(), prompt=prompt,
                           form=request.form if errors else {})


@bp.route("/journal/<int:entry_id>/delete", methods=("POST",))
@login_required
def delete_entry(entry_id):
    db = get_db()
    cur = db.execute("DELETE FROM mood_entries WHERE id = ? AND user_id = ?", (entry_id, g.user["id"]))
    db.commit()
    if cur.rowcount == 0:
        abort(404)
    flash("Entry deleted.", "info")
    return redirect(url_for("views.journal"))


# -------------------------------------------------------------- emotional analysis
@bp.route("/analyze", methods=("GET", "POST"))
@login_required
def analyze_page():
    uid = g.user["id"]
    db = get_db()
    if request.method == "POST":
        text = (request.form.get("text") or "").strip()
        if len(text) < 10:
            flash("Please write at least a sentence or two so the analysis has something to work with.", "warning")
        elif len(text) > 3000:
            flash("Please keep your text under 3000 characters.", "warning")
        else:
            res = analyze(text)
            cur = db.execute(
                "INSERT INTO analyses (user_id, created_at, text, primary_emotion, sentiment, distribution,"
                " evidence, distress, crisis) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (uid, utcnow(), text, res["primary"], res["sentiment"], json.dumps(res["distribution"]),
                 json.dumps(res["evidence"]), res["distress"], int(res["crisis"])),
            )
            db.commit()
            return redirect(url_for("views.analysis_result", analysis_id=cur.lastrowid))
    history = db.execute(
        "SELECT id, created_at, primary_emotion, distress, substr(text, 1, 80) AS snippet FROM analyses"
        " WHERE user_id = ? ORDER BY id DESC LIMIT 5", (uid,)
    ).fetchall()
    return render_template("analyze.html", result=None, summary=analytics.emotional_state_summary(uid),
                           history=history)


@bp.route("/analyze/<int:analysis_id>")
@login_required
def analysis_result(analysis_id):
    uid = g.user["id"]
    db = get_db()
    row = db.execute("SELECT * FROM analyses WHERE id = ? AND user_id = ?", (analysis_id, uid)).fetchone()
    if row is None:
        abort(404)
    result = {
        "row": row,
        "distribution": sorted(json.loads(row["distribution"]).items(), key=lambda kv: -kv[1]),
        "evidence": json.loads(row["evidence"]),
        "music_key": wellbeing.EMOTION_TO_MUSIC.get(row["primary_emotion"], "focus"),
    }
    history = db.execute(
        "SELECT id, created_at, primary_emotion, distress, substr(text, 1, 80) AS snippet FROM analyses"
        " WHERE user_id = ? ORDER BY id DESC LIMIT 5", (uid,)
    ).fetchall()
    return render_template("analyze.html", result=result, summary=analytics.emotional_state_summary(uid),
                           history=history)


@bp.route("/analyze/<int:analysis_id>/delete", methods=("POST",))
@login_required
def delete_analysis(analysis_id):
    db = get_db()
    db.execute("DELETE FROM analyses WHERE id = ? AND user_id = ?", (analysis_id, g.user["id"]))
    db.commit()
    flash("Analysis deleted.", "info")
    return redirect(url_for("views.analyze_page"))


# ---------------------------------------------------------------------------- chat
@bp.route("/chat")
@login_required
def chat():
    rows = get_db().execute(
        "SELECT role, content FROM (SELECT id, role, content FROM chat_messages WHERE user_id = ?"
        " ORDER BY id DESC LIMIT 40) ORDER BY id", (g.user["id"],)
    ).fetchall()
    return render_template("chat.html", messages=rows)


def _action_links(keys):
    links = []
    for key in keys:
        if key in CHAT_ACTIONS:
            label, endpoint, params = CHAT_ACTIONS[key]
            anchor = params.get("_anchor")
            url = url_for(endpoint)
            links.append({"label": label, "url": url + (f"#{anchor}" if anchor else "")})
    return links


@bp.route("/api/chat", methods=("POST",))
@login_required
def api_chat():
    uid = g.user["id"]
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("message", "")).strip()
    if not text:
        return jsonify(error="Please type a message."), 400
    if len(text) > 1000:
        return jsonify(error="Please keep messages under 1000 characters."), 400

    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    recent = db.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ? AND role = 'user' AND created_at > ?",
                        (uid, cutoff)).fetchone()[0]
    if recent >= 20:
        return jsonify(error="You're sending messages quickly. Take a breath and try again in a moment."), 429

    out = chatbot.reply(text, session.get("chat_state"))
    session["chat_state"] = out["state"]
    now = utcnow()
    db.execute("INSERT INTO chat_messages (user_id, role, content, emotion, created_at) VALUES (?, 'user', ?, ?, ?)",
               (uid, text, out["emotion"], now))
    db.execute("INSERT INTO chat_messages (user_id, role, content, emotion, created_at) VALUES (?, 'bot', ?, ?, ?)",
               (uid, out["text"], out["emotion"], now))
    db.commit()
    return jsonify(reply=out["text"], emotion=out["emotion"], crisis=out["crisis"],
                   actions=_action_links(out["actions"]))


@bp.route("/api/chat/clear", methods=("POST",))
@login_required
def api_chat_clear():
    db = get_db()
    db.execute("DELETE FROM chat_messages WHERE user_id = ?", (g.user["id"],))
    db.commit()
    session.pop("chat_state", None)
    return jsonify(ok=True)


# ------------------------------------------------------------ wellbeing and music
@bp.route("/wellbeing")
@login_required
def wellbeing_page():
    uid = g.user["id"]
    screening = analytics.latest_screening(uid)
    plan = wellbeing.personal_plan(g.user["user_type"], screening, analytics.recent_entries(uid, 14))
    return render_template("wellbeing.html", plan=plan, screening=screening)


@bp.route("/music")
@login_required
def music():
    uid = g.user["id"]
    key = request.args.get("mood")
    suggested = None
    if key not in wellbeing.MUSIC:
        row = get_db().execute(
            "SELECT primary_emotion FROM (SELECT primary_emotion, created_at FROM mood_entries WHERE user_id = ?"
            " AND primary_emotion IS NOT NULL UNION ALL SELECT primary_emotion, created_at FROM analyses"
            " WHERE user_id = ?) ORDER BY created_at DESC LIMIT 1", (uid, uid)
        ).fetchone()
        key = wellbeing.EMOTION_TO_MUSIC.get(row[0], "focus") if row else "focus"
        suggested = bool(row)
    return render_template("music.html", current=wellbeing.music_for(key), moods=wellbeing.MUSIC,
                           suggested=suggested)
