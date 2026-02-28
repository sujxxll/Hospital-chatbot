"""
Medical Knowledge Base.

Contains:
  1. Emergency keyword detection (rule-based safety net)
  2. Symptom → Department mapping
  3. Severity classification rules
  4. Department information

This acts as a fast, deterministic safety layer that runs BEFORE the LLM,
ensuring life-threatening keywords always trigger emergency escalation
even if the LLM misclassifies the input.
"""

# ── Emergency Keywords ─────────────────────────────────────────────────────
# These trigger IMMEDIATE emergency escalation regardless of LLM output.
# Organised by category for maintainability.

EMERGENCY_KEYWORDS: dict[str, list[str]] = {
    "cardiac": [
        "heart attack",
        "cardiac arrest",
        "chest tightness",
        "chest pressure",
        "crushing chest pain",
    ],
    "respiratory": [
        "can't breathe",
        "cannot breathe",
        "not breathing",
        "stopped breathing",
        "choking",
        "suffocating",
        "severe difficulty breathing",
    ],
    "neurological": [
        "stroke",
        "face drooping",
        "sudden numbness",
        "sudden confusion",
        "sudden severe headache",
        "seizure",
        "convulsions",
        "unconscious",
        "unresponsive",
        "loss of consciousness",
        "passed out",
        "fainted and not waking",
    ],
    "bleeding": [
        "severe bleeding",
        "uncontrollable bleeding",
        "won't stop bleeding",
        "hemorrhage",
        "coughing blood",
        "vomiting blood",
    ],
    "trauma": [
        "severe burn",
        "major accident",
        "head injury",
        "spinal injury",
        "broken neck",
    ],
    "toxicology": [
        "poisoning",
        "overdose",
        "swallowed poison",
        "drug overdose",
    ],
    "allergic": [
        "anaphylaxis",
        "anaphylactic shock",
        "severe allergic reaction",
        "throat swelling",
        "tongue swelling",
    ],
    "mental_health": [
        "suicidal",
        "want to kill myself",
        "ending my life",
        "self harm",
    ],
}

# Flatten for quick lookup
ALL_EMERGENCY_KEYWORDS: list[str] = [
    kw for category in EMERGENCY_KEYWORDS.values() for kw in category
]


# ── Symptom → Department Mapping ──────────────────────────────────────────

DEPARTMENT_MAPPING: dict[str, dict] = {
    "Cardiology": {
        "description": "Heart and cardiovascular system",
        "symptoms": [
            "chest pain", "heart palpitations", "high blood pressure",
            "irregular heartbeat", "shortness of breath with chest discomfort",
            "swollen legs", "dizziness with chest pain",
        ],
    },
    "Neurology": {
        "description": "Brain, spinal cord, and nervous system",
        "symptoms": [
            "headache", "migraine", "dizziness", "vertigo", "numbness",
            "tingling", "memory loss", "tremors", "balance problems",
            "blurred vision", "speech difficulty",
        ],
    },
    "Orthopedics": {
        "description": "Bones, joints, and musculoskeletal system",
        "symptoms": [
            "joint pain", "bone pain", "back pain", "fracture",
            "sprain", "muscle pain", "stiffness", "swollen joints",
            "difficulty walking", "knee pain", "shoulder pain",
        ],
    },
    "Gastroenterology": {
        "description": "Digestive system and gastrointestinal tract",
        "symptoms": [
            "stomach pain", "abdominal pain", "nausea", "vomiting",
            "diarrhea", "constipation", "bloating", "acid reflux",
            "heartburn", "loss of appetite", "blood in stool",
        ],
    },
    "Pulmonology": {
        "description": "Lungs and respiratory system",
        "symptoms": [
            "cough", "persistent cough", "wheezing", "shortness of breath",
            "breathing difficulty", "asthma", "chest congestion",
            "mucus production",
        ],
    },
    "Dermatology": {
        "description": "Skin, hair, and nail conditions",
        "symptoms": [
            "skin rash", "itching", "acne", "eczema", "psoriasis",
            "skin lesion", "hives", "skin discoloration", "mole changes",
            "hair loss",
        ],
    },
    "ENT (Ear, Nose & Throat)": {
        "description": "Ear, nose, throat, and related structures",
        "symptoms": [
            "ear pain", "hearing loss", "ringing in ears", "sore throat",
            "sinus pain", "nasal congestion", "nosebleed", "difficulty swallowing",
            "hoarse voice", "tonsillitis",
        ],
    },
    "Ophthalmology": {
        "description": "Eyes and vision",
        "symptoms": [
            "eye pain", "blurred vision", "double vision", "red eyes",
            "eye discharge", "vision loss", "floaters", "light sensitivity",
        ],
    },
    "Pediatrics": {
        "description": "Medical care for infants, children, and adolescents",
        "symptoms": [
            "child fever", "child rash", "child cough",
            "child vomiting", "child diarrhea", "child not eating",
            "child crying", "child ear infection",
        ],
        "indicators": ["child", "kid", "baby", "infant", "toddler", "son", "daughter"],
    },
    "Psychiatry": {
        "description": "Mental health and behavioral conditions",
        "symptoms": [
            "anxiety", "depression", "insomnia", "panic attacks",
            "mood swings", "stress", "hallucinations", "paranoia",
            "obsessive thoughts", "eating disorder",
        ],
    },
    "General Medicine": {
        "description": "General health concerns and primary care",
        "symptoms": [
            "fever", "fatigue", "weakness", "weight loss", "weight gain",
            "body aches", "chills", "sweating", "general discomfort",
            "cold", "flu", "infection",
        ],
    },
    "Urology": {
        "description": "Urinary tract and male reproductive system",
        "symptoms": [
            "painful urination", "frequent urination", "blood in urine",
            "kidney pain", "urinary incontinence",
        ],
    },
    "Gynecology": {
        "description": "Female reproductive system",
        "symptoms": [
            "menstrual irregularity", "pelvic pain", "vaginal discharge",
            "pregnancy concerns", "menstrual cramps",
        ],
    },
    "Emergency Medicine": {
        "description": "Life-threatening and critical conditions",
        "symptoms": [
            "severe pain", "high fever unresponsive to medication",
            "sudden collapse", "severe trauma",
        ],
    },
}


# ── Severity Rules ─────────────────────────────────────────────────────────
# These supplement the LLM's assessment with hard-coded safety rules.

CRITICAL_INDICATORS: list[str] = [
    "chest pain",
    "difficulty breathing",
    "severe bleeding",
    "loss of consciousness",
    "seizure",
    "stroke symptoms",
    "severe allergic reaction",
    "high fever in infant",
    "sudden vision loss",
    "severe head injury",
    "poisoning",
    "overdose",
    "suicidal thoughts",
]

MODERATE_INDICATORS: list[str] = [
    "persistent fever",
    "moderate pain",
    "recurring headache",
    "persistent vomiting",
    "blood in stool",
    "blood in urine",
    "swollen joints",
    "persistent cough lasting weeks",
    "unexplained weight loss",
]


def check_emergency_keywords(text: str) -> list[str]:
    """
    Fast rule-based emergency keyword check.
    Returns list of matched emergency keywords found in the text.
    This runs BEFORE the LLM as a safety net.
    """
    text_lower = text.lower()
    matches = []
    for keyword in ALL_EMERGENCY_KEYWORDS:
        if keyword in text_lower:
            matches.append(keyword)
    return matches


def get_department_info() -> str:
    """Return formatted department information for the LLM prompt."""
    lines = []
    for dept, info in DEPARTMENT_MAPPING.items():
        symptoms = ", ".join(info["symptoms"][:5])
        lines.append(f"- {dept}: {info['description']} (e.g. {symptoms})")
    return "\n".join(lines)
