# MindCare: AI-Based Mental Health Risk Screening and Support System

A responsive Flask web app that combines preliminary mental health screening, emotional-state analysis,
an AI support chatbot, mood journaling, personalised wellbeing activities, music suggestions, an interactive
dashboard and professional-help guidance in one platform.

> **MindCare is a screening and support tool. It does not diagnose, treat, or replace a qualified professional,
> and it is not an emergency service.**

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py                      # open http://127.0.0.1:5000
python -m pytest -q                # run the tests (22)
```

Python 3.10+ is recommended. The database (SQLite) and a generated secret key are created automatically in
`instance/` on first run. For production set `SECRET_KEY` yourself.

## Features by module

| Module | What it does | Where |
|---|---|---|
| 1. Authentication | Register, login, logout, profile, change password, delete account. Salted password hashes, signed HTTP-only session cookies, CSRF protection on every POST, login lockout after 5 failures, open-redirect protection. | `auth.py`, `security.py` |
| 2. Risk screening | **PHQ-4** (validated) + a safety item + six context items. Python scoring, Low/Moderate/High Concern, explanations, recommendations, history, "not a diagnosis" notices. | `screening.py` |
| 3. Emotional-state analysis | Hybrid lexicon + scikit-learn model. Emotion mix, sentiment, distress level, and the words that influenced the result. 14-day summary from the journal. | `emotion.py`, `analytics.py` |
| 4. AI chatbot | Crisis check first, then intent- and emotion-aware replies, with breathing, grounding, sleep, study, work, loneliness and motivation support. Conversations are stored and can be cleared. | `chatbot.py` |
| 5. Wellbeing suggestions | Exercises chosen from your screening answers, journal trends, and role (student / professional). Interactive box-breathing guide. | `wellbeing.py` |
| 6. Mood journal | Mood 1-5, sleep, stress, notes; analysed on save. | `views.py` |
| 7. Music | Mood-matched styles with YouTube/Spotify search links. No tracks are claimed, so nothing goes stale. | `wellbeing.py` |
| 8. Dashboard | Mood trend, emotion doughnut, screening history, streaks, weekly insights (Chart.js). | `analytics.py`, `dashboard.js` |
| 9. Professional guidance | Helplines, when to seek help, who to see, low-cost options, first-appointment tips. | `resources.py` |

## How the screening is scored

PHQ-4 (Kroenke et al., 2009; public domain): four items, each 0-3, over the last two weeks.
Items 1-2 are the anxiety subscale, items 3-4 the depression subscale. **A subscale score of 3 or more is a positive screen.**

| Total | Standard PHQ-4 band | MindCare category |
|---|---|---|
| 0-2 | Normal | Low Concern |
| 3-5 | Mild | Moderate Concern |
| 6-8 | Moderate | High Concern |
| 9-12 | Severe | High Concern |

- A **safety question** (wording from PHQ-9 item 9) escalates any answer above zero to High Concern and shows crisis resources.
- The six **context items** (sleep, concentration, energy, overwhelm, loneliness, irritability) are *not validated*, never change the category, and only personalise suggestions.

## Crisis safety

Every journal note, text analysis and chat message passes through `safety.detect_crisis()` first. A match shows
helplines and emergency guidance prominently. The detector is a deliberately conservative keyword net, not a clinical
assessment, so it will sometimes over-trigger. **If you swap the chatbot for an LLM, keep this check in front of it.**

Helplines (India) were checked in November 2026: Tele-MANAS 14416 / 1-800-891-4416, KIRAN 1800-599-0019 (24x7),
iCall 9152987821 (Mon-Sat, 8 am-9 pm), emergency 112. **Re-verify before any public launch** and edit `resources.py`
for other countries.

## Project layout

```
run.py                  entry point
mindcare/
  __init__.py           app factory, error pages, template filters
  db.py                 SQLite schema + helpers (standard library)
  security.py           sessions, CSRF, login_required, security headers
  auth.py  screening.py  views.py            routes (blueprints)
  emotion.py  chatbot.py  safety.py          AI / NLP
  wellbeing.py  analytics.py  resources.py   content + insights
  templates/  static/                        Bootstrap 5 UI, Chart.js dashboard
data/emotion_seed.csv   training examples for the ML model (extend this)
tests/test_app.py       22 tests: scoring, NLP, auth, CSRF, privacy, API
```

## Dependencies note

This build uses only Flask, scikit-learn and NumPy. It uses Python's built-in `sqlite3` instead of SQLAlchemy,
Flask's signed-cookie session with a small `login_required` decorator instead of Flask-Login, and its own CSRF and
login-throttle code instead of Flask-WTF. They were not installable where this was built, and the app does not need
them. If you prefer them, the data layer (`db.py`) and `security.py` are the only files to change.

## Limitations to be honest about

- The ML model is trained on a **small demonstration dataset** (64 sentences). It is blended with the lexicon engine
  so results are explainable, but accuracy is limited. For real use, retrain on a larger labelled corpus
  (for example GoEmotions) by replacing `data/emotion_seed.csv`.
- Text analysis can be wrong with sarcasm, slang, code-mixed Hinglish and very short text.
- The lexicon and chatbot are English-only.
- Screening results are preliminary. The app has not been clinically validated as a product, only its PHQ-4 questionnaire.

## Before going live

1. Set `SECRET_KEY` and `COOKIE_SECURE=1`, and serve over HTTPS (`gunicorn "mindcare:create_app()"` behind a reverse proxy).
2. Bootstrap and Chart.js load from the jsDelivr CDN. Self-host them or add Subresource Integrity hashes.
3. Add rate limiting at the proxy, regular database backups, and a privacy policy.
4. Mental health data is sensitive. Get legal advice on data-protection obligations (for example India's DPDP Act 2023) and have a clinician review the wording.
5. Consider email verification and password reset, which are not included.
