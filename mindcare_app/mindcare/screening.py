"""Module 2: PHQ-4 based risk screening, scoring and recommendations.

The Patient Health Questionnaire-4 (PHQ-4; Kroenke, Spitzer, Williams & Löwe, 2009)
is a validated 4-item ultra-brief screener for anxiety and depression. Items 1-2
form the anxiety subscale (GAD-2) and items 3-4 the depression subscale (PHQ-2).
A subscale score of 3 or more is the standard cut-off for a positive screen.

Scoring is deterministic and rule-based, so every result can be explained.

Outside the validated PHQ-4:
  * one safety item (wording from PHQ-9 item 9) - any answer above zero escalates
    the result to High Concern and shows crisis resources;
  * six "context" items on sleep, concentration, energy, overwhelm, loneliness and
    irritability. These are NOT validated, do not change the category, and are used
    only to personalise recommendations.
"""
import json

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .db import get_db, utcnow
from .security import login_required

bp = Blueprint("screening", __name__, url_prefix="/screening")

OPTIONS = [(0, "Not at all"), (1, "Several days"), (2, "More than half the days"), (3, "Nearly every day")]

PHQ4 = [
    {"id": "q1", "scale": "anxiety", "text": "Feeling nervous, anxious or on edge"},
    {"id": "q2", "scale": "anxiety", "text": "Not being able to stop or control worrying"},
    {"id": "q3", "scale": "depression", "text": "Little interest or pleasure in doing things"},
    {"id": "q4", "scale": "depression", "text": "Feeling down, depressed or hopeless"},
]
SAFETY = {"id": "s1", "text": "Thoughts that you would be better off dead, or of hurting yourself in some way"}
CONTEXT = [
    {"id": "c1", "flag": "sleep", "label": "Sleep difficulties",
     "text": "Trouble falling or staying asleep, or sleeping too much"},
    {"id": "c2", "flag": "concentration", "label": "Difficulty concentrating",
     "text": "Trouble concentrating on things like studying, working or reading"},
    {"id": "c3", "flag": "energy", "label": "Low energy", "text": "Feeling tired or having little energy"},
    {"id": "c4", "flag": "stress", "label": "Feeling overwhelmed",
     "text": "Feeling overwhelmed by academic, work or personal responsibilities"},
    {"id": "c5", "flag": "loneliness", "label": "Loneliness", "text": "Feeling lonely or cut off from other people"},
    {"id": "c6", "flag": "irritability", "label": "Irritability", "text": "Feeling irritable or easily angered"},
]
FLAG_LABELS = {c["flag"]: c["label"] for c in CONTEXT}

CATEGORY_STYLE = {"Low Concern": "success", "Moderate Concern": "warning", "High Concern": "danger"}
CATEGORY_MEANING = {
    "Low Concern": "Your answers suggest few or no symptoms of anxiety or low mood over the past two weeks.",
    "Moderate Concern": "Your answers suggest some symptoms of anxiety and/or low mood. They are worth paying attention to.",
    "High Concern": "Your answers suggest a significant level of distress. Speaking with a professional is recommended.",
}


def score_screening(answers: dict) -> dict:
    """Score a complete set of answers (q1-q4, s1, c1-c6; each an int 0-3)."""
    anxiety = answers["q1"] + answers["q2"]
    depression = answers["q3"] + answers["q4"]
    total = anxiety + depression

    # Standard PHQ-4 severity bands (Löwe et al., 2010).
    if total <= 2:
        band = "Normal"
    elif total <= 5:
        band = "Mild"
    elif total <= 8:
        band = "Moderate"
    else:
        band = "Severe"

    # MindCare's three-level category: Normal -> Low, Mild -> Moderate, Moderate/Severe -> High.
    if total <= 2:
        category = "Low Concern"
    elif total <= 5:
        category = "Moderate Concern"
    else:
        category = "High Concern"

    safety_flag = answers.get("s1", 0) > 0
    if safety_flag:
        category = "High Concern"

    flags = [c["flag"] for c in CONTEXT if answers.get(c["id"], 0) >= 2]
    return {
        "anxiety": anxiety,
        "depression": depression,
        "total": total,
        "band": band,
        "category": category,
        "anxiety_positive": anxiety >= 3,
        "depression_positive": depression >= 3,
        "safety_flag": safety_flag,
        "context_flags": flags,
    }


def parse_answers(form):
    """Return (answers, errors). Every question must be answered with 0-3."""
    answers, errors = {}, []
    for q in PHQ4 + [SAFETY] + CONTEXT:
        raw = form.get(q["id"])
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = None
        if value is None or not 0 <= value <= 3:
            errors.append(q["id"])
        else:
            answers[q["id"]] = value
    return answers, errors


def recommendations(result: dict, user_type: str) -> list:
    """Plain-language next steps based on the scored result."""
    cat = result["category"]
    recs = []
    if result["safety_flag"]:
        recs.append("You said you have had thoughts of being better off dead or of hurting yourself. "
                    "Please reach out now to a helpline below, a doctor, or someone you trust, "
                    "and call 112 if you may act on these thoughts.")
    if cat == "Low Concern":
        recs += [
            "Keep up the routines that support you: regular sleep, movement, meals, and time with people you like.",
            "Use the mood journal to notice changes early.",
            "Take this screening again in 2 to 4 weeks, or sooner if things change.",
        ]
    elif cat == "Moderate Concern":
        recs += [
            "Try the personalised exercises in the Wellbeing section, such as breathing, grounding and small daily activities.",
            "Talk to someone you trust about how you have been feeling.",
            "If these feelings continue for two weeks or start to affect your studies, work or relationships, "
            "consider seeing a counsellor, psychologist or doctor.",
            "Track your mood daily in the journal and take this screening again in about two weeks.",
        ]
    else:
        recs += [
            "We recommend speaking with a qualified mental health professional or your doctor soon.",
            "Reach out to someone you trust today. You do not have to manage this alone.",
            "Helplines can connect you with a trained counsellor right away, at no cost for the toll-free lines.",
            "In the meantime, gentle routines such as sleep, short walks and talking with people can help, "
            "but they are not a substitute for professional support.",
        ]
    if result["anxiety_positive"] and not result["depression_positive"]:
        recs.append("Your anxiety score reached the screening cut-off (3 or more). Worry and tension are worth discussing with a professional.")
    elif result["depression_positive"] and not result["anxiety_positive"]:
        recs.append("Your low-mood score reached the screening cut-off (3 or more). Low mood and loss of interest are worth discussing with a professional.")
    elif result["anxiety_positive"] and result["depression_positive"]:
        recs.append("Both your anxiety and low-mood scores reached the screening cut-off (3 or more). Discussing both with a professional is advisable.")
    if "stress" in result["context_flags"] or "concentration" in result["context_flags"]:
        if user_type == "student":
            recs.append("For academic pressure, break study into short focused blocks and speak to your college counsellor or a trusted teacher.")
        elif user_type == "professional":
            recs.append("For work pressure, list your top priorities, protect time to rest, and consider discussing workload with your manager or HR.")
    return recs


@bp.route("/", methods=("GET", "POST"))
@login_required
def take():
    previous = {}
    missing = []
    if request.method == "POST":
        answers, missing = parse_answers(request.form)
        previous = {k: request.form.get(k) for k in request.form}
        if missing:
            flash("Please answer every question so the result is accurate.", "warning")
        else:
            result = score_screening(answers)
            db = get_db()
            cur = db.execute(
                "INSERT INTO screenings (user_id, created_at, answers, anxiety_score, depression_score,"
                " total_score, severity_band, category, safety_flag, context_flags)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (g.user["id"], utcnow(), json.dumps(answers), result["anxiety"], result["depression"],
                 result["total"], result["band"], result["category"], int(result["safety_flag"]),
                 json.dumps(result["context_flags"])),
            )
            db.commit()
            return redirect(url_for("screening.result", screening_id=cur.lastrowid))
    return render_template("screening/form.html", phq4=PHQ4, safety=SAFETY, context=CONTEXT,
                           options=OPTIONS, previous=previous, missing=missing)


@bp.route("/<int:screening_id>")
@login_required
def result(screening_id):
    row = get_db().execute(
        "SELECT * FROM screenings WHERE id = ? AND user_id = ?", (screening_id, g.user["id"])
    ).fetchone()
    if row is None:
        abort(404)
    answers = json.loads(row["answers"])
    res = score_screening(answers)
    prev = get_db().execute(
        "SELECT total_score, category, created_at FROM screenings WHERE user_id = ? AND id < ?"
        " ORDER BY id DESC LIMIT 1", (g.user["id"], screening_id)
    ).fetchone()
    return render_template(
        "screening/result.html", row=row, res=res, prev=prev,
        recs=recommendations(res, g.user["user_type"]),
        style=CATEGORY_STYLE[res["category"]], meaning=CATEGORY_MEANING[res["category"]],
        flag_labels=FLAG_LABELS,
    )


@bp.route("/history")
@login_required
def history():
    rows = get_db().execute(
        "SELECT id, created_at, anxiety_score, depression_score, total_score, severity_band, category, safety_flag"
        " FROM screenings WHERE user_id = ? ORDER BY id DESC", (g.user["id"],)
    ).fetchall()
    return render_template("screening/history.html", rows=rows, styles=CATEGORY_STYLE)
