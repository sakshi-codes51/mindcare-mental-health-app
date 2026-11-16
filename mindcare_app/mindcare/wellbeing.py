"""Personalised wellbeing suggestions and music recommendations."""
from collections import Counter
from statistics import mean
from urllib.parse import quote, quote_plus

# --------------------------------------------------------------------- activities
LIBRARY = {
    "checkin": {
        "title": "Daily mood check-in", "icon": "\U0001F4D3", "minutes": "2 min",
        "steps": ["Rate your mood from 1 to 5 in the Journal.",
                  "Add one sentence about what shaped your day.",
                  "Note roughly how many hours you slept."],
    },
    "breathing": {
        "title": "Box breathing", "icon": "\U0001F32C️", "minutes": "3 min",
        "steps": ["Breathe in for 4 seconds, hold for 4, breathe out for 4, hold for 4.",
                  "Repeat for 4 to 6 rounds. Keep your shoulders relaxed.",
                  "If holding your breath feels uncomfortable, just breathe out for longer than you breathe in."],
    },
    "grounding": {
        "title": "5-4-3-2-1 grounding", "icon": "\U0001F33F", "minutes": "3 min",
        "steps": ["Name 5 things you can see and 4 you can touch.",
                  "Name 3 things you can hear, 2 you can smell and 1 you can taste.",
                  "Notice how your body feels when you finish."],
    },
    "worry_time": {
        "title": "Scheduled worry time", "icon": "\U0001F4DD", "minutes": "10 min",
        "steps": ["Pick a 10-minute slot each day for worrying, away from bedtime.",
                  "When a worry pops up earlier, jot it down and tell yourself you'll deal with it then.",
                  "In your slot, review the list and mark what you can act on and what is out of your control."],
    },
    "activation": {
        "title": "One small activity", "icon": "\U0001F6B6", "minutes": "10 min",
        "steps": ["Pick one small thing you used to enjoy or that gives a sense of achievement.",
                  "Do it for just 10 minutes, even if you don't feel like it.",
                  "Notice your mood afterwards and note it in your journal."],
    },
    "daylight": {
        "title": "Daylight and movement", "icon": "☀️", "minutes": "10-20 min",
        "steps": ["Step outside for a short walk, ideally in the morning light.",
                  "Leave your phone in your pocket for at least part of it.",
                  "Aim for most days rather than perfection."],
    },
    "self_compassion": {
        "title": "Speak to yourself kindly", "icon": "\U0001F49B", "minutes": "3 min",
        "steps": ["Notice a harsh thought about yourself.",
                  "Ask: what would I say to a friend who felt this way?",
                  "Write that kinder sentence down and read it back."],
    },
    "sleep": {
        "title": "Sleep wind-down", "icon": "\U0001F319", "minutes": "30 min",
        "steps": ["Keep a regular wake-up time, even on weekends.",
                  "Avoid screens and caffeine in the hour before bed (and caffeine after midday).",
                  "Write tomorrow's to-do list earlier in the evening so your mind can let go.",
                  "If you can't sleep after about 20 minutes, get up, do something calm, then return to bed."],
    },
    "focus": {
        "title": "Focus blocks", "icon": "⏱️", "minutes": "25 min",
        "steps": ["Pick one task and silence notifications.",
                  "Work for 25 minutes, then take a real 5-minute break away from screens.",
                  "After four blocks, take a longer 15 to 30 minute break."],
    },
    "study": {
        "title": "Exam-stress study plan", "icon": "\U0001F4DA", "minutes": "15 min",
        "steps": ["List every topic and rank it by marks and time left.",
                  "Schedule the highest-value topics in your best energy hours.",
                  "Plan one realistic goal per day, and include breaks, meals and sleep.",
                  "If you feel stuck, talk to a teacher or your college counsellor."],
    },
    "work": {
        "title": "Workday boundaries", "icon": "\U0001F4BC", "minutes": "10 min",
        "steps": ["Each morning, write your top three priorities.",
                  "Take a short break every 60 to 90 minutes.",
                  "Set a clear end to your workday and avoid checking work messages after it.",
                  "If your workload is consistently unmanageable, raise it with your manager or HR."],
    },
    "braindump": {
        "title": "Brain dump and prioritise", "icon": "\U0001F9E0", "minutes": "10 min",
        "steps": ["Write down everything on your mind, without sorting it.",
                  "Circle the 1 to 3 items that truly matter today.",
                  "Schedule or drop the rest. Cross things off as you go."],
    },
    "connection": {
        "title": "Reach out to one person", "icon": "\U0001F91D", "minutes": "5 min",
        "steps": ["Pick someone you trust or used to be close to.",
                  "Send a short message: a hello, a meme, or 'free to chat this week?'.",
                  "Consider one regular group activity, such as a club, class or sports group."],
    },
    "pause": {
        "title": "Pause before reacting", "icon": "✋", "minutes": "2 min",
        "steps": ["Notice the early signs of irritation in your body.",
                  "Pause, breathe out slowly, and step away if you can.",
                  "Come back when you are calmer and decide how to respond."],
    },
    "energy": {
        "title": "Gentle energy boost", "icon": "⚡", "minutes": "10 min",
        "steps": ["Drink water and have a proper meal.",
                  "Move your body for a few minutes: stretch or walk.",
                  "Get some natural light, and keep naps short (20 minutes or less)."],
    },
    "gratitude": {
        "title": "Three good things", "icon": "\U0001F338", "minutes": "3 min",
        "steps": ["Before bed, write down three things that went okay today.",
                  "Add a short note on why each happened.",
                  "Doing this regularly is a simple way to keep wellbeing steady."],
    },
}


def personal_plan(user_type, screening, entries):
    """Choose activities and explain why, using only what the user has actually reported."""
    flags = set(screening["context_flags"]) if screening else set()
    anxiety_pos = bool(screening and screening["anxiety_score"] >= 3)
    depression_pos = bool(screening and screening["depression_score"] >= 3)
    emotions = Counter(e["primary_emotion"] for e in entries if e["primary_emotion"])
    moods = [e["mood"] for e in entries]
    sleeps = [e["sleep_hours"] for e in entries if e["sleep_hours"] is not None]
    avg_mood = mean(moods) if moods else None
    avg_sleep = mean(sleeps) if sleeps else None

    plan, seen = [], set()

    def add(key, reason):
        if key not in seen and len(plan) < 8:
            seen.add(key)
            plan.append({**LIBRARY[key], "key": key, "reason": reason})

    add("checkin", "Regular check-ins make your patterns visible over time.")

    if anxiety_pos or emotions["anxiety"] >= 2:
        why = "Your latest screening showed anxiety symptoms." if anxiety_pos else "Anxious feelings showed up in your recent entries."
        add("breathing", why)
        add("grounding", why)
        if anxiety_pos:
            add("worry_time", why)
    if depression_pos or emotions["sadness"] >= 2 or (avg_mood is not None and avg_mood <= 2.5):
        why = ("Your latest screening showed low mood or loss of interest." if depression_pos
               else "Your recent mood ratings have been on the low side.")
        add("activation", why)
        add("daylight", why)
        add("self_compassion", why)
    if "sleep" in flags or (avg_sleep is not None and avg_sleep < 6):
        add("sleep", "You reported sleep difficulties or short sleep recently.")
    if "concentration" in flags:
        add("focus", "You reported trouble concentrating.")
    if "stress" in flags or emotions["stress"] >= 2:
        why = "You reported feeling overwhelmed, or stress appeared in your recent entries."
        add("braindump", why)
        if user_type == "student":
            add("study", why)
        elif user_type == "professional":
            add("work", why)
    elif "concentration" in flags and user_type == "student":
        add("study", "Concentration difficulty can build up around study pressure.")
    if "loneliness" in flags or emotions["loneliness"] >= 2:
        add("connection", "You reported feeling lonely or cut off from others.")
    if "irritability" in flags or emotions["anger"] >= 2:
        add("pause", "You reported irritability or anger.")
    if "energy" in flags:
        add("energy", "You reported low energy.")
    if len(plan) <= 1:
        add("gratitude", "Nothing in your recent data suggests a specific concern. Here are steady habits.")
        add("breathing", "A quick calming tool is useful to have ready.")
    return plan


# ------------------------------------------------------------------------- music
MUSIC = {
    "stressed": {
        "label": "Stressed or overwhelmed", "goal": "Slow your body down and lower tension",
        "why": "Slow, steady, mostly instrumental music with around 60 to 80 beats per minute can help the body relax.",
        "styles": [("Ambient piano", "ambient piano relaxing"), ("Soft instrumental (flute, santoor or sitar)", "santoor relaxing instrumental"),
                   ("Nature sounds", "rain and forest sounds relaxing")],
    },
    "anxious": {
        "label": "Anxious or restless", "goal": "Steady your breathing and quiet racing thoughts",
        "why": "Predictable, slow music with no sudden changes gives your mind something steady to follow while you breathe slowly.",
        "styles": [("Calm acoustic guitar", "calm acoustic guitar instrumental"), ("Slow Indian classical (raag) instrumentals", "slow raag instrumental relaxing"),
                   ("Soft lo-fi", "soft lofi calm")],
    },
    "sad": {
        "label": "Sad or low", "goal": "Feel understood first, then lift gently",
        "why": "A common music-therapy approach is to begin with music that matches your mood and then move step by step toward gentler, brighter pieces.",
        "styles": [("Gentle acoustic or piano ballads", "gentle acoustic songs comforting"), ("Warm, mellow instrumentals", "warm mellow instrumental"),
                   ("Soft uplifting pop", "soft uplifting feel good songs")],
    },
    "angry": {
        "label": "Angry or frustrated", "goal": "Release energy safely, then cool down",
        "why": "Some people find that energetic music helps release tension, and that a slow cool-down afterwards brings the body back to calm.",
        "styles": [("Energetic workout playlist (to release it)", "energetic workout music"), ("Then slow instrumental to cool down", "slow calming instrumental"),
                   ("Deep, steady drums or tabla", "tabla instrumental calm")],
    },
    "lonely": {
        "label": "Lonely", "goal": "Feel connected and comforted",
        "why": "Warm, familiar music and voices can feel like company, and it can make reaching out to someone feel easier.",
        "styles": [("Warm singer-songwriter music", "warm singer songwriter acoustic"), ("Comforting old favourites", "comforting nostalgic songs"),
                   ("Cosy cafe jazz", "cosy cafe jazz")],
    },
    "tired": {
        "label": "Tired or low energy", "goal": "Gently raise your energy",
        "why": "Moderate-tempo, upbeat music can raise alertness without feeling harsh.",
        "styles": [("Light upbeat acoustic", "upbeat acoustic feel good"), ("Morning walk playlist", "morning walk music uplifting"),
                   ("Easy-going pop", "feel good pop")],
    },
    "happy": {
        "label": "Happy or celebrating", "goal": "Savour and extend the good mood",
        "why": "Music can amplify positive moods. Share a playlist with a friend to strengthen connection.",
        "styles": [("Feel-good pop", "feel good pop hits"), ("Dance and singalong", "dance singalong playlist"),
                   ("Upbeat Bollywood or regional favourites", "upbeat bollywood feel good")],
    },
    "sleep": {
        "label": "Can't sleep", "goal": "Wind down for rest",
        "why": "Very slow, quiet, sparse music and steady natural sounds can help the body shift toward sleep when played softly.",
        "styles": [("Sleep piano", "sleep piano soft"), ("Gentle night raag instrumentals", "night raag instrumental sleep"),
                   ("Rain or ocean sounds", "rain sounds for sleeping")],
    },
    "focus": {
        "label": "Focus or study", "goal": "Support concentration",
        "why": "Music without lyrics, at a low volume, tends to be less distracting than songs with words when you're reading or studying.",
        "styles": [("Lo-fi beats", "lofi beats study"), ("Instrumental classical", "classical piano study"),
                   ("Soft electronic or ambient", "ambient focus music")],
    },
}

EMOTION_TO_MUSIC = {
    "stress": "stressed", "anxiety": "anxious", "sadness": "sad", "anger": "angry",
    "loneliness": "lonely", "joy": "happy", "calm": "focus", "neutral": "focus",
}


def music_for(key: str) -> dict:
    """Return the music category with search links (no specific tracks are claimed)."""
    cat = MUSIC.get(key, MUSIC["focus"])
    styles = [
        {
            "name": name,
            "youtube": "https://www.youtube.com/results?search_query=" + quote_plus(query),
            "spotify": "https://open.spotify.com/search/" + quote(query),
        }
        for name, query in cat["styles"]
    ]
    return {"key": key if key in MUSIC else "focus", "label": cat["label"], "goal": cat["goal"],
            "why": cat["why"], "styles": styles}
