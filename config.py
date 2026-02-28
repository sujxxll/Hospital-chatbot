"""
Configuration module for the Healthcare Chatbot.
Loads environment variables and provides application-wide settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ───────────────────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── MongoDB ────────────────────────────────────────────────────────────────
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "hospital_colab_chatbot")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "appointments")

# ── Application Settings ──────────────────────────────────────────────────
APP_TITLE = "🏥 Healthcare Triage Assistant"
APP_DESCRIPTION = (
    "A conversational healthcare assistant that helps assess your symptoms, "
    "recommends the appropriate hospital department, and books appointments."
)

# ── LLM Settings ──────────────────────────────────────────────────────────
MAX_CONVERSATION_TURNS = 50
TEMPERATURE = 0.3  # Lower temperature for more consistent medical responses
TOP_P = 0.9
MAX_OUTPUT_TOKENS = 1024
