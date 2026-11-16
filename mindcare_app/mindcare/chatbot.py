"""AI chatbot support: crisis-aware, emotion-aware, rule-based supportive conversation.

This is not a therapist and does not give medical advice. It offers empathic
reflection, evidence-informed self-help techniques (breathing, grounding, sleep
hygiene, study/work pacing) and signposts professional help. It runs fully
offline. To use a hosted LLM instead, replace `reply()` but KEEP the crisis check
that runs before anything else.
"""
import random
import re

from .emotion import NEGATIVE, analyze
from .resources import HELPLINES
from .safety import detect_crisis, normalise

CRISIS_REPLY = (
    "I'm really glad you told me, and I'm concerned about you. You deserve support right now, from a real person.\n\n"
    "If you might act on these thoughts, or you are in immediate danger, please call 112 now or go to the nearest "
    "emergency room.\n\n"
    "You can also talk to a trained counsellor right away:\n"
    + "\n".join(f"• {h['name'].split(' (')[0]}: {h['numbers'][0]} ({h['hours']})" for h in HELPLINES)
    + "\n\nOutside India, findahelpline.com lists services by country.\n\n"
    "If you can, please tell someone near you, such as a friend, family member or roommate, and ask them to stay "
    "with you. I'm an automated tool and can't replace that, but I'm here in this chat."
)

OPENERS = {
    "sadness": [
        "I'm sorry you're feeling this low. Thank you for putting it into words.",
        "That sounds heavy, and it matters that you said it out loud.",
        "It sounds like things feel really hard right now.",
    ],
    "anxiety": [
        "That sounds really uncomfortable. Anxiety can make everything feel urgent.",
        "I hear how on edge you are. You're not alone in feeling this way.",
        "Worry can be exhausting. Thank you for sharing it.",
    ],
    "anger": [
        "It sounds like something has really frustrated you, and that's a valid feeling.",
        "I can hear how upset you are. Anger often shows up when something matters to us.",
    ],
    "stress": [
        "That sounds like a lot to carry at once.",
        "It sounds like you're under real pressure right now.",
        "Feeling stretched thin is exhausting. Thank you for telling me.",
    ],
    "loneliness": [
        "Feeling alone can hurt a lot, and many people go through it, especially during big life changes.",
        "I'm glad you shared that. Loneliness is a real and painful feeling.",
    ],
    "joy": [
        "That's lovely to hear!",
        "I'm really glad things are going well for you.",
    ],
    "calm": [
        "It's good to hear you're feeling steadier.",
        "That sounds like a peaceful place to be.",
    ],
    "neutral": [
        "Thanks for sharing that with me.",
        "I'm listening.",
    ],
}

FOLLOW_UPS = {
    "sadness": ["How long have you been feeling this way?", "Is there something specific behind it, or does it feel more general?"],
    "anxiety": ["What is your mind focusing on the most right now?", "When did you start to notice the worry building?"],
    "anger": ["What happened that set this off?", "What do you most need right now: to vent, or to find a way forward?"],
    "stress": ["What is the one thing weighing on you the most?", "What feels most urgent, and what could wait?"],
    "loneliness": ["Is there someone you used to feel close to that you could reach out to?", "When do you feel the loneliness most?"],
    "joy": ["What do you think contributed to it?", "What would help you keep more of this in your week?"],
    "calm": ["What helped you get to this place?", "Is there anything you'd like to keep doing to hold onto this?"],
    "neutral": ["How have you been feeling lately, in general?", "Is there something on your mind you'd like to talk through?"],
}

BREATHING = (
    "Let's try box breathing together. Sit comfortably and let your shoulders drop.\n"
    "1. Breathe in slowly through your nose for 4 seconds.\n"
    "2. Hold gently for 4 seconds.\n"
    "3. Breathe out through your mouth for 4 seconds.\n"
    "4. Hold for 4 seconds.\n"
    "Repeat for about 4 rounds. If holding your breath feels uncomfortable, skip the holds and just make your "
    "exhale longer than your inhale. How do you feel afterwards?"
)
GROUNDING = (
    "Here is the 5-4-3-2-1 grounding exercise. Go slowly and, if you can, say each answer out loud:\n"
    "• 5 things you can see\n• 4 things you can feel or touch\n• 3 things you can hear\n"
    "• 2 things you can smell\n• 1 thing you can taste\n"
    "It brings your attention back to the present moment. How did that feel?"
)
JOURNAL_PROMPT = (
    "Try writing for five minutes without editing yourself. You could start with: "
    "\"Right now I'm feeling... because...\", then \"One thing I can control today is...\". "
    "You can save it in your Journal and the app will track how your mood changes over time."
)
STUDY_PLAN = (
    "Here is a simple way to reset study stress:\n"
    "1. Write down everything you need to cover, then rank it by marks and time left.\n"
    "2. Study in 25-minute focused blocks with 5-minute breaks.\n"
    "3. Plan one small, achievable goal for today instead of the whole syllabus.\n"
    "4. Protect your sleep. Memory and focus both depend on it.\n"
    "Would it help to talk about what feels most overwhelming?"
)

AFFIRM_RE = re.compile(r"^\s*(yes|yeah|yep|yup|sure|ok|okay|please|go ahead|let'?s do it|show me|sounds good)\b", re.I)

INTENTS = [
    ("greeting", re.compile(r"^\s*(hi|hello|hey|hii+|namaste|good (morning|afternoon|evening))\b", re.I)),
    ("thanks", re.compile(r"\b(thanks|thank you|thx|appreciate it)\b", re.I)),
    ("bye", re.compile(r"\b(bye|goodbye|see you|good night|gtg)\b", re.I)),
    ("identity", re.compile(r"\b(who are you|what are you|are you (a )?(human|real|bot|ai|therapist|doctor|person))\b", re.I)),
    ("capabilities", re.compile(r"\b(what can you do|how does this work|what do you do|how can you help)\b", re.I)),
    ("panic", re.compile(r"\b(panic|panicking|can'?t breathe|heart (is )?racing)\b", re.I)),
    ("breathing", re.compile(r"\b(breath|breathing|breathe|calm (me )?down)\b", re.I)),
    ("grounding", re.compile(r"\b(ground(ing)?|5-4-3-2-1)\b", re.I)),
    ("professional", re.compile(r"\b(therapist|counsel(l)?or|psychologist|psychiatrist|professional help|see a doctor|need help)\b", re.I)),
    ("sleep", re.compile(r"\b(sleep|sleeping|insomnia|awake all night|nightmares?)\b", re.I)),
    ("exam", re.compile(r"\b(exams?|study|studying|assignments?|grades?|marks|viva|semester|backlog|placements?)\b", re.I)),
    ("work", re.compile(r"\b(my job|at work|workplace|boss|manager|office|burn(ed|t)?[- ]?out|deadlines?|colleagues?|career)\b", re.I)),
    ("lonely", re.compile(r"\b(lonely|alone|no friends|isolated|homesick|left out)\b", re.I)),
    ("motivation", re.compile(r"\b(motivat\w*|procrastinat\w*|lazy|can'?t focus|no energy|unmotivated)\b", re.I)),
    ("anger", re.compile(r"\b(angry|furious|mad|rage|irritat\w*|frustrat\w*)\b", re.I)),
    ("journal", re.compile(r"\b(journal|diary|write (it )?down)\b", re.I)),
    ("music", re.compile(r"\b(music|songs?|playlist)\b", re.I)),
]


def _pick(options):
    return random.choice(options)


def detect_intent(text: str):
    for name, pattern in INTENTS:
        if pattern.search(text):
            return name
    return None


def _reflect(emotion: str) -> str:
    return _pick(OPENERS.get(emotion, OPENERS["neutral"]))


def _intent_reply(intent: str, emotion: str):
    """Return (text, offer, actions) for a detected intent."""
    if intent == "greeting":
        return ("Hello, and welcome. I'm here to listen and to share some simple coping tools. "
                "How are you feeling today?", None, [])
    if intent == "thanks":
        return ("You're very welcome. Looking after your wellbeing takes effort, and you're doing it. "
                "Is there anything else on your mind?", None, [])
    if intent == "bye":
        return ("Take care of yourself. Come back any time, and remember a quick mood check-in in the journal "
                "helps you spot patterns.", None, ["journal"])
    if intent == "identity":
        return ("I'm an automated support assistant built into MindCare. I'm not a human, therapist or doctor, "
                "and I can't diagnose anything. I can listen, suggest coping exercises and point you to "
                "professional help.", None, ["help"])
    if intent == "capabilities":
        return ("I can listen to how you're feeling, guide you through breathing or grounding exercises, "
                "help with exam or work stress, sleep, loneliness and motivation, and point you to professional "
                "support. What would you like to start with?", None, ["screening", "wellbeing"])
    if intent == "panic":
        return ("If you're feeling panicky, you're safe and this will pass. Try to breathe out slowly, longer than "
                "you breathe in, and press your feet into the floor. Would you like me to guide you through a "
                "breathing exercise?", "breathing", ["breathing"])
    if intent == "breathing":
        return (BREATHING, None, ["breathing"])
    if intent == "grounding":
        return (GROUNDING, None, [])
    if intent == "professional":
        return ("Reaching out to a professional is a strong and sensible step. A counsellor, clinical psychologist "
                "or psychiatrist can assess what's going on and help you with it. Your college counselling "
                "centre, a government hospital OPD, or a helpline like Tele-MANAS (14416) are good starting "
                "points. The Help section lists options and how to prepare for a first appointment.",
                None, ["help"])
    if intent == "sleep":
        return ("Sleep and mood are closely linked. A few things that help: keep a regular wake-up time, avoid "
                "screens for 30-60 minutes before bed, skip caffeine after midday, and write tomorrow's worries "
                "on paper earlier in the evening so your mind can let go. If poor sleep lasts for weeks, "
                "please mention it to a doctor. What does your night usually look like?", None, ["wellbeing"])
    if intent == "exam":
        return (_reflect("stress") + " " + STUDY_PLAN, None, ["wellbeing"])
    if intent == "work":
        return (_reflect("stress") + " Some things that often help with work stress: list your top three priorities "
                "for the day, take short real breaks, and set a clear end to your workday. If the workload is "
                "constantly unmanageable, it's reasonable to discuss it with your manager. What part of work "
                "is weighing on you most?", None, ["wellbeing"])
    if intent == "lonely":
        return (_reflect("loneliness") + " Small steps count: message one person you haven't spoken to in a while, "
                "join a club or class, or spend time around others, even just studying in a library or cafe. "
                "Would you like to talk about what's making it hard to connect?", None, ["wellbeing"])
    if intent == "motivation":
        return ("Low motivation is often a sign of tiredness or low mood rather than laziness. Try the "
                "two-minute rule: pick one small task and commit to just two minutes. Starting is usually the "
                "hardest part. What is one tiny thing you could do right now?", None, ["wellbeing"])
    if intent == "anger":
        return (_reflect("anger") + " When anger is high, pause before reacting: breathe out slowly, step away "
                "for a few minutes, or move your body. Then you can decide what to do. Would you like to "
                "tell me what happened?", None, [])
    if intent == "journal":
        return (JOURNAL_PROMPT, None, ["journal"])
    if intent == "music":
        return ("Music can really shift how you feel. Tell me your mood, or visit the Music page, where I suggest "
                "styles for stress, sadness, focus or sleep.", None, ["music"])
    return None


def reply(text: str, state: dict | None = None) -> dict:
    """Produce a reply. `state` carries a pending offer between turns (kept in the session)."""
    state = state or {}
    text = normalise(text).strip()

    # 1. Safety first, always.
    if detect_crisis(text):
        return {"text": CRISIS_REPLY, "emotion": "crisis", "crisis": True, "actions": ["help"], "state": {}}

    analysis = analyze(text)
    emotion = analysis["primary"]

    # 2. Follow up on an offered exercise ("yes", "okay", ...).
    offer = state.get("offer")
    if offer and AFFIRM_RE.match(text):
        content = {"breathing": BREATHING, "grounding": GROUNDING, "journal": JOURNAL_PROMPT}.get(offer)
        if content:
            return {"text": content, "emotion": emotion, "crisis": False,
                    "actions": ["breathing"] if offer == "breathing" else [], "state": {}}

    # 3. Intent-specific replies.
    intent = detect_intent(text)
    if intent:
        out = _intent_reply(intent, emotion)
        if out:
            body, new_offer, actions = out
            if analysis["distress"] == "high" and intent not in {"professional", "panic", "greeting", "bye"}:
                body += ("\n\nIt sounds like a lot is going on. Talking with a counsellor or doctor can really help, "
                         "and the Help page has options if you'd like them.")
                if "help" not in actions:
                    actions = actions + ["help"]
            return {"text": body, "emotion": emotion, "crisis": False, "actions": actions,
                    "state": {"offer": new_offer} if new_offer else {}}

    # 4. General emotion-aware reflection.
    parts = [_reflect(emotion)]
    actions, new_offer = [], None
    if emotion in NEGATIVE:
        if analysis["distress"] == "high":
            parts.append("It sounds like you're carrying a lot. If this has been going on for a while, speaking "
                         "with a counsellor or doctor can make a real difference.")
            actions.append("help")
        if emotion in {"anxiety", "stress"}:
            parts.append("If it would help, I can walk you through a short breathing exercise.")
            new_offer = "breathing"
            actions.append("breathing")
        elif emotion in {"sadness", "loneliness"}:
            parts.append("Writing about it can sometimes help. Would you like a journaling prompt?")
            new_offer = "journal"
        elif emotion == "anger":
            parts.append("Slow breathing can take the edge off strong anger. Want to try a quick round?")
            new_offer = "breathing"
    parts.append(_pick(FOLLOW_UPS.get(emotion, FOLLOW_UPS["neutral"])))
    return {"text": " ".join(parts), "emotion": emotion, "crisis": False, "actions": actions,
            "state": {"offer": new_offer} if new_offer else {}}
