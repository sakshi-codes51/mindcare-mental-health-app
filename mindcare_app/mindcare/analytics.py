"""Mood analytics for the dashboard: series, distributions, streaks and plain-language insights."""
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from math import sqrt
from statistics import mean

from .db import get_db

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _since(days: int) -> str:
    return (_today() - timedelta(days=days)).isoformat()


def recent_entries(user_id: int, days: int = 30) -> list:
    rows = get_db().execute(
        "SELECT * FROM mood_entries WHERE user_id = ? AND entry_date >= ? ORDER BY entry_date, id",
        (user_id, _since(days)),
    ).fetchall()
    return [dict(r) for r in rows]


def latest_screening(user_id: int):
    row = get_db().execute(
        "SELECT * FROM screenings WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["context_flags"] = json.loads(data["context_flags"] or "[]")
    return data


def mood_series(user_id: int, days: int = 30) -> list:
    by_day = defaultdict(list)
    for e in recent_entries(user_id, days):
        by_day[e["entry_date"]].append(e["mood"])
    return [{"date": d, "mood": round(mean(v), 2), "n": len(v)} for d, v in sorted(by_day.items())]


def emotion_distribution(user_id: int, days: int = 30) -> list:
    db = get_db()
    since = _since(days)
    counts = Counter()
    for r in db.execute(
        "SELECT primary_emotion FROM mood_entries WHERE user_id = ? AND entry_date >= ? AND primary_emotion IS NOT NULL",
        (user_id, since),
    ):
        counts[r[0]] += 1
    for r in db.execute(
        "SELECT primary_emotion FROM analyses WHERE user_id = ? AND substr(created_at, 1, 10) >= ?",
        (user_id, since),
    ):
        counts[r[0]] += 1
    return [{"label": k, "count": v} for k, v in counts.most_common()]


def screening_series(user_id: int) -> list:
    rows = get_db().execute(
        "SELECT created_at, anxiety_score, depression_score, total_score, category FROM screenings"
        " WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    return [{"date": r["created_at"][:10], "total": r["total_score"], "anxiety": r["anxiety_score"],
             "depression": r["depression_score"], "category": r["category"]} for r in rows]


def streak(user_id: int) -> int:
    """Consecutive days with a check-in, ending at the latest entry (if it is recent)."""
    rows = get_db().execute(
        "SELECT DISTINCT entry_date FROM mood_entries WHERE user_id = ? ORDER BY entry_date DESC LIMIT 400",
        (user_id,),
    ).fetchall()
    if not rows:
        return 0
    days = [date.fromisoformat(r[0]) for r in rows]
    # Allow for the user's local date being a day ahead of or behind UTC.
    if abs((_today() - days[0]).days) > 1:
        return 0
    count, expected = 0, days[0]
    for d in days:
        if d == expected:
            count += 1
            expected -= timedelta(days=1)
        else:
            break
    return count


def _avg(values):
    return round(mean(values), 2) if values else None


def summary_stats(user_id: int) -> dict:
    last7 = recent_entries(user_id, 6)
    prev7 = [e for e in recent_entries(user_id, 13) if e not in last7]
    entries30 = recent_entries(user_id, 30)
    sleeps = [e["sleep_hours"] for e in last7 if e["sleep_hours"] is not None]
    n_screen = get_db().execute("SELECT COUNT(*) FROM screenings WHERE user_id = ?", (user_id,)).fetchone()[0]
    return {
        "entries_30d": len(entries30),
        "avg_mood_7d": _avg([e["mood"] for e in last7]),
        "avg_mood_prev": _avg([e["mood"] for e in prev7]),
        "avg_sleep_7d": _avg(sleeps),
        "streak": streak(user_id),
        "screenings": n_screen,
    }


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = mean(xs), mean(ys)
    sx = sqrt(sum((x - mx) ** 2 for x in xs))
    sy = sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def insights(user_id: int) -> list:
    """Short, plain-language observations. These describe patterns, not causes."""
    entries = recent_entries(user_id, 60)
    if not entries:
        return ["Add your first mood check-in in the Journal to start seeing patterns here."]
    out = []

    this_week = [e["mood"] for e in entries if e["entry_date"] >= _since(6)]
    last_week = [e["mood"] for e in entries if _since(13) <= e["entry_date"] < _since(6)]
    if len(this_week) >= 2 and len(last_week) >= 2:
        a, b = mean(this_week), mean(last_week)
        if a - b >= 0.5:
            out.append(f"Your average mood this week ({a:.1f}/5) is higher than last week ({b:.1f}/5).")
        elif b - a >= 0.5:
            out.append(f"Your average mood this week ({a:.1f}/5) is lower than last week ({b:.1f}/5). "
                       "Be extra kind to yourself and consider talking to someone you trust.")
        else:
            out.append(f"Your mood has been fairly steady: {a:.1f}/5 this week and {b:.1f}/5 last week.")

    if len(entries) >= 10:
        by_wd = defaultdict(list)
        for e in entries:
            by_wd[date.fromisoformat(e["entry_date"]).weekday()].append(e["mood"])
        avgs = {wd: mean(v) for wd, v in by_wd.items() if len(v) >= 2}
        if len(avgs) >= 3:
            best, worst = max(avgs, key=avgs.get), min(avgs, key=avgs.get)
            if avgs[best] - avgs[worst] >= 0.8:
                out.append(f"Your mood tends to be lowest on {WEEKDAYS[worst]}s ({avgs[worst]:.1f}/5) "
                           f"and highest on {WEEKDAYS[best]}s ({avgs[best]:.1f}/5).")

    paired = [(e["sleep_hours"], e["mood"]) for e in entries if e["sleep_hours"] is not None]
    if len(paired) >= 7:
        r = _pearson([p[0] for p in paired], [p[1] for p in paired])
        if r is not None and r >= 0.4:
            out.append("On days when you logged more sleep, your mood tended to be higher. "
                       "This is a pattern in your own data, not proof of cause.")

    if len(entries) >= 3 and all(e["mood"] <= 2 for e in entries[-3:]):
        out.append("Your last three check-ins were low. If this continues, please consider reaching out "
                   "to a counsellor, doctor or someone you trust.")

    s = streak(user_id)
    if s >= 3:
        out.append(f"You have checked in {s} days in a row. Nice consistency.")
    return out or ["Keep checking in. A few more entries will reveal clearer patterns."]


def emotional_state_summary(user_id: int, days: int = 14):
    """Plain-language overview of recent emotional state from journal entries."""
    entries = recent_entries(user_id, days)
    if not entries:
        return None
    counts = Counter(e["primary_emotion"] for e in entries if e["primary_emotion"])
    moods = [e["mood"] for e in entries]
    sentiments = [e["sentiment"] for e in entries if e["sentiment"] is not None]
    level = {"low": 0, "moderate": 1, "high": 2}
    distress_vals = [level[e["distress"]] for e in entries if e["distress"] in level]
    avg_distress = mean(distress_vals) if distress_vals else 0
    overall = "low" if avg_distress < 0.6 else "moderate" if avg_distress < 1.4 else "high"

    trend = "not enough data"
    if len(moods) >= 4:
        half = len(moods) // 2
        diff = mean(moods[half:]) - mean(moods[:half])
        trend = "improving" if diff >= 0.4 else "declining" if diff <= -0.4 else "steady"

    return {
        "days": days,
        "n": len(entries),
        "top_emotions": counts.most_common(3),
        "avg_mood": round(mean(moods), 2),
        "avg_sentiment": round(mean(sentiments), 2) if sentiments else None,
        "trend": trend,
        "distress": overall,
    }
