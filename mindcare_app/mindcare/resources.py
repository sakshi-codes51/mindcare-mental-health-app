"""Static professional-guidance content: helplines, when to seek help, how to find care.

Helpline details were checked against official or primary sources in
November 2026 (Tele-MANAS and KIRAN: PIB press releases; iCall: icallhelpline.org).
Numbers and hours change - re-verify before any public deployment.
"""

HELPLINES = [
    {
        "name": "Tele-MANAS (Government of India)",
        "numbers": ["14416", "1-800-891-4416"],
        "tel": "14416",
        "hours": "Toll-free, 24x7",
        "note": "National tele-mental-health service with trained counsellors.",
    },
    {
        "name": "KIRAN (Ministry of Social Justice and Empowerment)",
        "numbers": ["1800-599-0019"],
        "tel": "18005990019",
        "hours": "Toll-free, 24x7, 13 languages",
        "note": "Mental health support and crisis helpline.",
    },
    {
        "name": "iCall (Tata Institute of Social Sciences)",
        "numbers": ["9152987821"],
        "tel": "9152987821",
        "hours": "Monday to Saturday, 8 am to 9 pm",
        "note": "Psychosocial counselling by trained professionals. Email: icall@tiss.ac.in",
    },
]

EMERGENCY = {"name": "Emergency services (India)", "number": "112"}
INTERNATIONAL = {"name": "Find a Helpline (by country)", "url": "https://findahelpline.com"}

WHEN_TO_SEEK_HELP = [
    "Low mood, anxiety, or loss of interest that lasts two weeks or more.",
    "Your studies, work, or relationships are being affected.",
    "Big changes in sleep or appetite, or constant exhaustion.",
    "Panic attacks, or worry that feels impossible to switch off.",
    "Pulling away from friends and family, or using alcohol or other substances to cope.",
    "Any thoughts of hurting yourself or ending your life. This is urgent: contact a helpline or emergency services right away.",
]

PROFESSIONALS = [
    {
        "title": "General physician (GP)",
        "text": "A good first stop. Can check for physical causes (for example thyroid problems or anaemia) and refer you onward.",
    },
    {
        "title": "Psychiatrist",
        "text": "A medical doctor who can diagnose mental health conditions and prescribe medication when it is needed.",
    },
    {
        "title": "Clinical psychologist",
        "text": "Provides assessment and talking therapies such as cognitive behavioural therapy (CBT). In India, look for Rehabilitation Council of India (RCI) registration.",
    },
    {
        "title": "Counsellor",
        "text": "Offers supportive counselling for stress, exam pressure, relationships and coping skills. Many colleges and workplaces have one.",
    },
]

ACCESS_OPTIONS = [
    "Your college or university counselling centre, usually free for enrolled students.",
    "Your employer's employee assistance programme (EAP), if there is one.",
    "Psychiatry outpatient departments (OPD) at government hospitals, and the District Mental Health Programme.",
    "Tele-MANAS and other helplines, which work from anywhere and need no appointment.",
    "Online or phone counselling, which removes travel and can fit around your schedule.",
    "Peer-support groups and NGOs that offer low-cost or sliding-scale counselling.",
]

FIRST_APPOINTMENT_TIPS = [
    "Write down what you have noticed, when it started and how often it happens.",
    "Note changes in sleep, appetite, energy and concentration.",
    "Bring a list of any medicines or supplements you take.",
    "Think about what you want from the visit, and write your questions down.",
    "You can bring a trusted friend or family member for support.",
    "Ask about fees, how long sessions last, and how your information is kept confidential.",
]
