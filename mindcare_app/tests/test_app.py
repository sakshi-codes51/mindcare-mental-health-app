import json
import re
import tempfile
from pathlib import Path

import pytest

from mindcare import create_app
from mindcare.chatbot import reply
from mindcare.emotion import analyze
from mindcare.safety import detect_crisis
from mindcare.screening import score_screening

ZERO = {"q1": 0, "q2": 0, "q3": 0, "q4": 0, "s1": 0, "c1": 0, "c2": 0, "c3": 0, "c4": 0, "c5": 0, "c6": 0}


def answers(**over):
    return {**ZERO, **over}


# --------------------------------------------------------------------- scoring
def test_scoring_bands_and_categories():
    assert score_screening(answers())["category"] == "Low Concern"
    assert score_screening(answers(q1=1, q2=1))["category"] == "Low Concern"          # total 2
    r = score_screening(answers(q1=1, q2=1, q3=1))                                    # total 3
    assert (r["category"], r["band"]) == ("Moderate Concern", "Mild")
    assert score_screening(answers(q1=3, q2=2))["category"] == "Moderate Concern"     # total 5
    r = score_screening(answers(q1=3, q2=3))                                          # total 6
    assert (r["category"], r["band"]) == ("High Concern", "Moderate")
    r = score_screening(answers(q1=3, q2=3, q3=3, q4=3))
    assert (r["total"], r["band"], r["category"]) == (12, "Severe", "High Concern")


def test_subscale_cutoffs_and_safety_escalation():
    r = score_screening(answers(q1=2, q2=1))
    assert r["anxiety_positive"] and not r["depression_positive"]
    r = score_screening(answers(q3=1, q4=1))
    assert not r["depression_positive"]
    r = score_screening(answers(s1=1))
    assert r["safety_flag"] and r["category"] == "High Concern" and r["total"] == 0


def test_context_flags_do_not_change_category():
    r = score_screening(answers(c1=3, c2=3, c4=2))
    assert r["category"] == "Low Concern"
    assert set(r["context_flags"]) == {"sleep", "concentration", "stress"}


# --------------------------------------------------------------- emotion + safety
def test_emotion_basic():
    assert analyze("I feel so anxious and my heart is racing, I'm really worried")["primary"] == "anxiety"
    assert analyze("I'm so happy and proud today, everything is wonderful")["primary"] == "joy"
    assert analyze("I have deadlines and exams and I'm completely overwhelmed")["primary"] == "stress"
    assert analyze("I'm lonely and have no friends here")["primary"] == "loneliness"


def test_emotion_negation_and_sentiment():
    assert analyze("I am not happy at all")["sentiment"] < 0
    assert analyze("I am not anxious anymore")["sentiment"] > 0
    assert analyze("I am delighted and grateful")["sentiment"] > 0.25
    res = analyze("I went to the market and bought vegetables")
    assert res["distress"] == "low"


def test_distress_levels():
    assert analyze("I'm sad, hopeless, anxious and overwhelmed, I can't cope and feel so alone")["distress"] == "high"
    assert analyze("Today was great, I feel calm and relaxed")["distress"] == "low"


def test_crisis_detection():
    assert detect_crisis("I want to die")
    assert detect_crisis("I’ve been thinking about suicide")
    assert detect_crisis("i want to hurt myself")
    assert not detect_crisis("I could kill for a coffee")
    assert not detect_crisis("This exam is killing me")
    assert analyze("I want to end my life")["crisis"]


def test_chatbot_crisis_and_intents():
    out = reply("I want to kill myself")
    assert out["crisis"] and "14416" in out["text"] and "112" in out["text"]
    assert not reply("hello")["crisis"]
    assert "box breathing" in reply("can you guide me through breathing")["text"].lower()
    r = reply("I feel really anxious about tomorrow")
    assert r["state"].get("offer") == "breathing"
    follow = reply("yes please", r["state"])
    assert "breathe in" in follow["text"].lower()


# ----------------------------------------------------------------- web app flows
@pytest.fixture()
def client():
    tmp = tempfile.mkdtemp()
    app = create_app({"TESTING": True, "DATABASE": str(Path(tmp) / "t.sqlite3"), "SECRET_KEY": "test-key"})
    return app.test_client()


def token(client, path="/login"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)


def post(client, url, data=None, path="/login", **kw):
    data = dict(data or {})
    data["_csrf"] = token(client, path)
    return client.post(url, data=data, **kw)


def register(client, email="a@example.com", name="Asha Verma", password="Secret123", user_type="student"):
    return post(client, "/register", {
        "name": name, "email": email, "password": password, "confirm": password, "user_type": user_type,
        "age_group": "18-24", "adult": "on", "ack": "on"}, path="/register", follow_redirects=True)


def test_public_pages(client):
    for url in ["/", "/about", "/help", "/login", "/register"]:
        assert client.get(url).status_code == 200
    assert client.get("/nope").status_code == 404


def test_protected_pages_redirect(client):
    for url in ["/dashboard", "/screening/", "/journal", "/analyze", "/chat", "/wellbeing", "/music", "/profile"]:
        r = client.get(url)
        assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert client.post("/api/chat", json={"message": "hi"}).status_code in (302, 400)


def test_csrf_enforced(client):
    r = client.post("/login", data={"email": "a@b.co", "password": "x"})
    assert r.status_code == 400


def test_register_validation_and_duplicate(client):
    r = post(client, "/register", {"name": "A", "email": "bad", "password": "short", "confirm": "short"}, path="/register")
    body = r.get_data(as_text=True)
    assert "valid email" in body and "at least 8" in body and "18 or older" in body
    assert "Welcome to MindCare" in register(client).get_data(as_text=True)
    post(client, "/logout", path="/dashboard")
    assert "already exists" in register(client).get_data(as_text=True)


def test_password_is_hashed(client):
    register(client)
    import sqlite3
    row = sqlite3.connect(client.application.config["DATABASE"]).execute("SELECT password_hash FROM users").fetchone()
    assert "Secret123" not in row[0] and row[0].startswith(("scrypt:", "pbkdf2:"))


def test_login_logout_and_lockout(client):
    register(client)
    post(client, "/logout", path="/dashboard")
    assert client.get("/dashboard").status_code == 302
    bad = post(client, "/login", {"email": "a@example.com", "password": "wrongpass1"})
    assert "Incorrect email or password" in bad.get_data(as_text=True)
    ok = post(client, "/login", {"email": "a@example.com", "password": "Secret123"}, follow_redirects=True)
    assert "Hello, Asha" in ok.get_data(as_text=True)
    post(client, "/logout", path="/dashboard")
    for _ in range(5):
        post(client, "/login", {"email": "a@example.com", "password": "nope12345"})
    locked = post(client, "/login", {"email": "a@example.com", "password": "Secret123"})
    assert "Too many failed attempts" in locked.get_data(as_text=True)


def test_open_redirect_blocked(client):
    register(client)
    post(client, "/logout", path="/dashboard")
    r = post(client, "/login?next=//evil.com", {"email": "a@example.com", "password": "Secret123"})
    assert r.status_code == 302 and "evil.com" not in r.headers["Location"]


def full_form(**over):
    return {**{k: str(v) for k, v in answers().items()}, **{k: str(v) for k, v in over.items()}}


def test_screening_flow_and_privacy(client):
    register(client)
    r = post(client, "/screening/", {"q1": "1"}, path="/screening/")
    assert "answer every question" in r.get_data(as_text=True)

    r = post(client, "/screening/", full_form(q1=2, q2=1, q3=1, q4=1, c1=3), path="/screening/", follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "Moderate Concern" in body and "not a medical diagnosis" in body and "Positive screen" in body
    assert "Sleep difficulties" in body

    r = post(client, "/screening/", full_form(s1=1), path="/screening/", follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "High Concern" in body and "14416" in body and "Safety flag" not in body

    assert "Safety flag" in client.get("/screening/history").get_data(as_text=True)

    # a second user can't open the first user's results
    post(client, "/logout", path="/dashboard")
    register(client, email="b@example.com", name="Ben")
    assert client.get("/screening/1").status_code == 404


def test_journal_analysis_dashboard(client):
    register(client)
    r = post(client, "/journal", {"mood": "2", "sleep_hours": "5", "stress": "4",
                                  "note": "I'm so anxious and overwhelmed about exams"}, path="/journal", follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "Check-in saved" in body and "Stress" in body
    assert "between 0 and 24" in post(client, "/journal", {"mood": "3", "sleep_hours": "99"}, path="/journal").get_data(as_text=True)
    assert "choose how you are feeling" in post(client, "/journal", {"note": "x"}, path="/journal").get_data(as_text=True)

    r = post(client, "/journal", {"mood": "1", "note": "I want to die"}, path="/journal", follow_redirects=True)
    assert "You are not alone" in r.get_data(as_text=True)

    r = post(client, "/analyze", {"text": "I feel lonely and sad, nobody calls me anymore"}, path="/analyze", follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "Emotion mix" in body and "not a diagnosis" in body

    dash = client.get("/dashboard").get_data(as_text=True)
    assert 'id="chart-data"' in dash and "Mood over the last 30 days" in dash
    data = json.loads(re.search(r'id="chart-data">(.*?)</script>', dash, re.S).group(1))
    assert len(data["mood"]) >= 1 and data["emotions"]

    assert client.get("/wellbeing").status_code == 200
    assert "YouTube" in client.get("/music?mood=sleep").get_data(as_text=True)
    assert client.get("/music").status_code == 200


def test_journal_delete_only_own(client):
    register(client)
    post(client, "/journal", {"mood": "4", "note": "good day"}, path="/journal")
    post(client, "/logout", path="/dashboard")
    register(client, email="b@example.com", name="Ben")
    assert post(client, "/journal/1/delete", path="/journal").status_code == 404


def test_chat_api(client):
    register(client)
    t = token(client, "/chat")
    h = {"X-CSRF-Token": t}
    r = client.post("/api/chat", json={"message": "I'm so stressed about my exams"}, headers=h)
    assert r.status_code == 200 and r.get_json()["reply"]
    r = client.post("/api/chat", json={"message": "I want to end my life"}, headers=h)
    assert r.get_json()["crisis"] is True and "14416" in r.get_json()["reply"]
    assert client.post("/api/chat", json={"message": ""}, headers=h).status_code == 400
    assert client.post("/api/chat", json={"message": "x" * 1001}, headers=h).status_code == 400
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 400  # no CSRF header
    assert "stressed about my exams" in client.get("/chat").get_data(as_text=True)
    assert client.post("/api/chat/clear", headers=h).get_json()["ok"]
    assert "stressed about my exams" not in client.get("/chat").get_data(as_text=True)


def test_chat_message_is_escaped(client):
    register(client)
    t = token(client, "/chat")
    client.post("/api/chat", json={"message": "<script>alert(1)</script>"}, headers={"X-CSRF-Token": t})
    assert "<script>alert(1)</script>" not in client.get("/chat").get_data(as_text=True)


def test_profile_update_and_delete_account(client):
    register(client)
    r = post(client, "/profile", {"name": "Asha V", "user_type": "professional", "age_group": "25-34"}, path="/profile", follow_redirects=True)
    assert "Profile updated" in r.get_data(as_text=True)
    r = post(client, "/profile/password", {"current": "Secret123", "new": "Better4567", "confirm": "Better4567"}, path="/profile", follow_redirects=True)
    assert "Password changed" in r.get_data(as_text=True)
    post(client, "/journal", {"mood": "3", "note": "fine"}, path="/journal")
    bad = post(client, "/profile/delete", {"password": "wrong"}, path="/profile", follow_redirects=True)
    assert "not deleted" in bad.get_data(as_text=True)
    ok = post(client, "/profile/delete", {"password": "Better4567"}, path="/profile", follow_redirects=True)
    assert "permanently deleted" in ok.get_data(as_text=True)
    import sqlite3
    con = sqlite3.connect(client.application.config["DATABASE"])
    assert con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM mood_entries").fetchone()[0] == 0


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Frame-Options"] == "DENY" and "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "no-store"
