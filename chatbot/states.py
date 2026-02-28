"""
Conversation State Machine.

Defines all possible conversation states and valid transitions.
The state machine ensures the chatbot follows a safe, structured flow:

  GREETING → SYMPTOM_COLLECTION → SEVERITY_ASSESSMENT
     ↓               ↓                    ↓
     └─── (any) ─────┴─── EMERGENCY ←────┘
                      ↓
              DEPARTMENT_RECOMMENDATION → APPOINTMENT_OFFER
                                              ↓
                                      COLLECTING_DETAILS → BOOKING_CONFIRMATION → COMPLETED
"""

from enum import Enum


class ConversationState(Enum):
    """All possible states in the healthcare triage conversation."""

    GREETING = "greeting"
    SYMPTOM_COLLECTION = "symptom_collection"
    SEVERITY_ASSESSMENT = "severity_assessment"
    EMERGENCY = "emergency"
    DEPARTMENT_RECOMMENDATION = "department_recommendation"
    APPOINTMENT_OFFER = "appointment_offer"
    COLLECTING_DETAILS = "collecting_details"
    BOOKING_CONFIRMATION = "booking_confirmation"
    COMPLETED = "completed"


# ── Valid State Transitions ────────────────────────────────────────────────
# Maps each state to a set of states it can transition to.
# EMERGENCY can be reached from ANY state (safety override).

VALID_TRANSITIONS: dict[str, set[str]] = {
    "greeting": {
        "symptom_collection",
        "emergency",
    },
    "symptom_collection": {
        "symptom_collection",     # continue collecting
        "severity_assessment",
        "emergency",
    },
    "severity_assessment": {
        "emergency",
        "department_recommendation",
        "symptom_collection",     # need more info
    },
    "emergency": {
        "emergency",              # stay in emergency
        "greeting",               # new conversation after emergency
    },
    "department_recommendation": {
        "appointment_offer",
        "symptom_collection",     # user has additional concerns
        "emergency",
    },
    "appointment_offer": {
        "collecting_details",
        "completed",              # user declines
        "symptom_collection",     # user has more symptoms
        "emergency",
    },
    "collecting_details": {
        "collecting_details",     # still collecting
        "booking_confirmation",
        "emergency",
    },
    "booking_confirmation": {
        "completed",
        "collecting_details",     # user wants to change details
        "emergency",
    },
    "completed": {
        "greeting",               # start new conversation
        "symptom_collection",     # new issue
    },
}


def is_valid_transition(current_state: str, next_state: str) -> bool:
    """Check if a state transition is valid. Emergency is always valid."""
    if next_state == "emergency":
        return True
    allowed = VALID_TRANSITIONS.get(current_state, set())
    return next_state in allowed


# ── State Display Labels ──────────────────────────────────────────────────

STATE_LABELS: dict[str, str] = {
    "greeting": "👋 Welcome",
    "symptom_collection": "🔍 Collecting Symptoms",
    "severity_assessment": "⚖️ Assessing Severity",
    "emergency": "🚨 EMERGENCY DETECTED",
    "department_recommendation": "🏥 Department Recommendation",
    "appointment_offer": "📋 Appointment Offered",
    "collecting_details": "📝 Collecting Details",
    "booking_confirmation": "✅ Confirming Booking",
    "completed": "🎉 Completed",
}
