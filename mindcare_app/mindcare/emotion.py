"""Module 3: emotional-state analysis.

A hybrid of two transparent techniques:

1. A rule-based lexicon engine with negation, intensifier and phrase handling.
   It is explainable: it reports which words influenced the result.
2. A small scikit-learn model (TF-IDF + logistic regression) trained at start-up on
   data/emotion_seed.csv. The seed set is a demonstration size; for production,
   retrain on a larger labelled corpus.

The output is an estimate of the emotional tone of a piece of writing. It is not a
diagnosis and can be wrong, especially with sarcasm, slang or very short text.
"""
import csv
import re
import threading
from pathlib import Path

from .safety import detect_crisis, normalise

EMOTIONS = ["joy", "calm", "sadness", "anxiety", "anger", "stress", "loneliness", "neutral"]
NEGATIVE = {"sadness", "anxiety", "anger", "stress", "loneliness"}
POSITIVE = {"joy", "calm"}
SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "emotion_seed.csv"


def _terms(emotion, weight, words):
    return {w: (emotion, weight) for w in words.split()}


_EXACT = {}
for _e, _w, _words in [
    ("joy", 1.0, "happy happier happiest glad joy joyful excited exciting great wonderful grateful thankful proud "
                 "cheerful delighted thrilled blessed energetic confident fantastic awesome amazing hopeful optimistic "
                 "relieved motivated accomplished love loved loving"),
    ("joy", 0.7, "fun enjoy enjoyed enjoying smile smiling smiled laugh laughed laughing content positive"),
    ("joy", 0.5, "good better"),
    ("calm", 1.0, "calm calmer relaxed relaxing relax peaceful peace serene rested centered tranquil unhurried"),
    ("calm", 0.6, "steady balanced comfortable settled safe"),
    ("calm", 0.4, "okay"),
    ("calm", 0.3, "fine"),
    ("sadness", 1.0, "sad sadly sadness saddened depressed depression hopeless hopelessness cry crying cried tears "
                     "tearful empty unhappy miserable heartbroken grief grieving worthless numb despair pointless "
                     "meaningless gloomy"),
    ("sadness", 0.7, "disappointed disappointing regret regrets ashamed guilty failure"),
    ("sadness", 0.6, "hurt hurts hurting"),
    ("sadness", 0.5, "down"),
    ("sadness", 0.4, "low lost"),
    ("anxiety", 1.0, "anxious anxiety worry worried worries worrying nervous panic panicking panicked fear fears "
                     "afraid scared dread dreading uneasy restless tense overthinking overthink apprehensive "
                     "terrified jittery palpitations trembling shaky frightened"),
    ("anxiety", 0.6, "insecure nauseous"),
    ("anger", 1.0, "angry anger mad furious irritated irritating irritable annoyed annoying frustrated frustrating "
                   "frustration rage resent resentful resentment hate hated hating hostile bitter outraged livid "
                   "infuriating snapped yelling yelled"),
    ("stress", 1.0, "stress stressed stressful stressing overwhelmed overwhelming overwhelm pressure pressured burnout "
                    "exhausted exhausting exhaustion deadline deadlines exams exam workload swamped overworked drained "
                    "fatigue fatigued backlog hectic"),
    ("stress", 0.7, "juggling"),
    ("stress", 0.6, "tired"),
    ("stress", 0.4, "assignments behind"),
    ("loneliness", 1.0, "lonely loneliness lonesome isolated isolation abandoned disconnected homesick unloved "
                        "excluded friendless"),
    ("loneliness", 0.9, "nobody"),
    ("loneliness", 0.8, "alone invisible"),
    ("loneliness", 0.7, "ignored"),
    ("loneliness", 0.6, "misunderstood"),
]:
    _EXACT.update(_terms(_e, _w, _words))

_PHRASES = {
    "anxiety": {"on edge": 1.0, "what if": 0.7, "can't breathe": 1.0, "cannot breathe": 1.0, "heart racing": 1.0,
                "heart is racing": 1.0, "racing thoughts": 1.0, "worst case": 0.8, "something bad": 0.7},
    "stress": {"burnt out": 1.2, "burned out": 1.2, "too much": 0.8, "can't cope": 1.2, "cannot cope": 1.2,
               "falling behind": 1.0, "no time": 0.7, "to do list": 0.5, "to-do list": 0.5, "under pressure": 1.0,
               "can't keep up": 1.0, "cannot keep up": 1.0, "can't sleep": 0.8},
    "sadness": {"no motivation": 1.0, "don't enjoy": 0.9, "lost interest": 1.0, "no energy": 0.6, "feel empty": 1.0,
                "feeling empty": 1.0, "give up": 0.9, "can't stop crying": 1.2, "nothing matters": 1.0,
                "get out of bed": 0.7},
    "loneliness": {"no one": 0.8, "no friends": 1.2, "left out": 1.0, "by myself": 0.7, "on my own": 0.6,
                   "nobody cares": 1.2, "feel alone": 1.0},
    "anger": {"fed up": 1.0, "sick of": 0.8},
    "joy": {"looking forward": 0.8, "can't wait": 0.7, "feel great": 1.0, "so proud": 1.0},
    "calm": {"at ease": 1.0, "at peace": 1.0, "slept well": 0.8, "feel relaxed": 1.0},
}
_PHRASE_LIST = sorted(
    ((re.compile(r"\b" + re.escape(p) + r"\b"), emo, w) for emo, d in _PHRASES.items() for p, w in d.items()),
    key=lambda t: -len(t[0].pattern),
)

NEGATORS = {"not", "no", "never", "cannot", "can't", "cant", "don't", "dont", "won't", "wont", "isn't", "isnt",
            "wasn't", "aren't", "didn't", "didnt", "doesn't", "doesnt", "hardly", "barely", "without", "none",
            "neither", "nor", "wouldn't", "couldn't", "shouldn't", "haven't", "hasn't", "hadn't", "ain't"}
INTENSIFIERS = {"very", "really", "extremely", "so", "too", "totally", "completely", "constantly", "always",
                "incredibly", "utterly", "deeply", "terribly"}
DAMPENERS = {"slightly", "somewhat", "bit", "kinda", "sorta", "mildly"}
_TOKEN_RE = re.compile(r"[a-z']+")
_SENTENCE_SPLIT = re.compile(r"[.!?;\n]+")


def _lexicon_scores(text: str):
    """Return (emotion_scores, positive_mass, negative_mass, evidence_terms)."""
    text = normalise(text).lower()
    scores = {e: 0.0 for e in EMOTIONS}
    pos = neg = 0.0
    evidence = []

    def add(emotion, weight, term):
        nonlocal pos, neg
        scores[emotion] += weight
        if emotion in POSITIVE:
            pos += weight
        elif emotion in NEGATIVE:
            neg += weight
        if term not in evidence:
            evidence.append(term)

    # Multi-word phrases first; remove them so words are not double counted.
    for pattern, emotion, weight in _PHRASE_LIST:
        for m in pattern.finditer(text):
            add(emotion, weight, m.group(0))
        text = pattern.sub(" . ", text)

    for sentence in _SENTENCE_SPLIT.split(text):
        tokens = _TOKEN_RE.findall(sentence)
        for i, tok in enumerate(tokens):
            hit = _EXACT.get(tok)
            if not hit:
                continue
            emotion, weight = hit
            before3 = tokens[max(0, i - 3):i]
            before2 = tokens[max(0, i - 2):i]
            if any(t in INTENSIFIERS for t in before2):
                weight *= 1.5
            if any(t in DAMPENERS for t in before2):
                weight *= 0.6
            if any(t in NEGATORS for t in before3):
                # "not anxious" -> a little calm; "not happy" -> a little sadness.
                if emotion in NEGATIVE:
                    add("calm", 0.5 * weight, "not " + tok)
                elif emotion in POSITIVE:
                    add("sadness", 0.4 * weight, "not " + tok)
            else:
                add(emotion, weight, tok)
    return scores, pos, neg, evidence


_model = None
_model_tried = False
_model_lock = threading.Lock()


def _get_model():
    global _model, _model_tried
    if _model_tried:
        return _model
    with _model_lock:
        if _model_tried:
            return _model
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import make_pipeline

            with open(SEED_PATH, encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            model = make_pipeline(
                TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
                LogisticRegression(max_iter=2000, C=10),
            )
            model.fit([r["text"] for r in rows], [r["label"] for r in rows])
            _model = model
        except Exception:  # scikit-learn missing or data unreadable: lexicon-only mode
            _model = None
        _model_tried = True
    return _model


def _ml_probs(text: str):
    model = _get_model()
    if model is None or not text.strip():
        return None
    probs = model.predict_proba([normalise(text)])[0]
    out = {e: 0.0 for e in EMOTIONS}
    out.update({label: float(p) for label, p in zip(model.classes_, probs)})
    return out


def _clamp(x, lo=-1.0, hi=1.0):
    return max(lo, min(hi, x))


def analyze(text: str) -> dict:
    """Analyse the emotional tone of free text."""
    text = (text or "").strip()
    crisis = detect_crisis(text)
    lex, pos, neg, evidence = _lexicon_scores(text)
    ml = _ml_probs(text)
    lex_total = sum(lex.values())

    if lex_total > 0:
        lex_dist = {e: lex[e] / lex_total for e in EMOTIONS}
        dist = {e: 0.65 * lex_dist[e] + 0.35 * ml[e] for e in EMOTIONS} if ml else lex_dist
    elif ml:
        dist = ml
    else:
        dist = {e: 0.0 for e in EMOTIONS}
        dist["neutral"] = 1.0
    total = sum(dist.values()) or 1.0
    dist = {e: dist[e] / total for e in EMOTIONS}

    ml_sent = None
    if ml:
        ml_sent = 0.8 * (sum(ml[e] for e in POSITIVE) - sum(ml[e] for e in NEGATIVE))
    lex_sent = (pos - neg) / (pos + neg + 1.0)
    if lex_total > 0 and ml_sent is not None:
        sentiment = 0.7 * lex_sent + 0.3 * ml_sent
    elif lex_total > 0:
        sentiment = lex_sent
    else:
        sentiment = ml_sent or 0.0
    sentiment = _clamp(sentiment)

    neg_mass = sum(dist[e] for e in NEGATIVE)
    intensity = min(1.0, neg / 4.0)
    distress_score = 0.6 * neg_mass * (0.5 + 0.5 * intensity) + 0.4 * max(0.0, -sentiment)
    distress = "low" if distress_score < 0.35 else "moderate" if distress_score < 0.7 else "high"
    if crisis:
        distress = "high"

    primary = max(EMOTIONS, key=lambda e: dist[e])
    label = "positive" if sentiment > 0.25 else "negative" if sentiment < -0.25 else "neutral / mixed"
    return {
        "primary": primary,
        "confidence": round(dist[primary], 3),
        "distribution": {e: round(dist[e], 3) for e in EMOTIONS},
        "sentiment": round(sentiment, 3),
        "sentiment_label": label,
        "distress": distress,
        "distress_score": round(distress_score, 3),
        "crisis": crisis,
        "evidence": evidence[:10],
        "engine": "hybrid (lexicon + ML)" if ml else "lexicon only",
    }
