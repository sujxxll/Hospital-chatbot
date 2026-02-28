"""
Conversation Manager — Core Orchestrator.

This is the brain of the healthcare chatbot. It:
  1. Runs rule-based emergency detection BEFORE the LLM (safety net)
  2. Sends context-aware prompts to the LLM
  3. Parses and validates LLM responses
  4. Manages conversation state transitions
  5. Handles appointment booking via MongoDB
  6. Detects and handles intent switching

Architecture:
  User Input
      │
      ▼
  ┌──────────────┐
  │  Emergency    │──── MATCH ────▶ Immediate Escalation
  │  Keyword Scan │
  └──────┬───────┘
         │ NO MATCH
         ▼
  ┌──────────────┐
  │  LLM Engine  │──── Structured JSON Response
  │  (Gemini)    │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  State       │──── Validate & enforce transitions
  │  Machine     │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  MongoDB     │──── Save appointment (if booking)
  │  (optional)  │
  └──────────────┘
"""

from chatbot.llm_engine import LLMEngine
from chatbot.medical_knowledge import check_emergency_keywords
from chatbot.states import is_valid_transition, STATE_LABELS
from database.mongo_client import MongoDBClient
import config


def create_initial_context() -> dict:
    """Create a fresh conversation context."""
    return {
        "state": "greeting",
        "symptoms": [],
        "severity": None,
        "department": None,
        "is_emergency": False,
        "appointment": {
            "patient_name": None,
            "preferred_date": None,
            "preferred_time": None,
            "contact_number": None,
        },
        "history": [],
        "booking_id": None,
    }


class ConversationManager:
    """
    Orchestrates the healthcare triage conversation.

    This class is intentionally stateless regarding conversation context —
    context is passed in and returned, making it compatible with Gradio's
    gr.State serialization.
    """

    def __init__(self, llm_engine: LLMEngine, db_client: MongoDBClient):
        self.llm = llm_engine
        self.db = db_client

    def process_message(self, user_message: str, context: dict) -> tuple[str, dict]:
        """
        Process a user message and return (bot_response, updated_context).

        This is the main entry point for each conversation turn.
        """
        user_message = user_message.strip()
        if not user_message:
            return "Please type a message to get started.", context

        # ── Step 0: Enforce conversation turn limit ─────────────────────
        turn_count = sum(1 for m in context["history"] if m["role"] == "user")
        if turn_count >= config.MAX_CONVERSATION_TURNS:
            return (
                "⚠️ This conversation has reached the maximum number of turns. "
                "Please click **🔄 New Conversation** to start fresh.",
                context,
            )

        # ── Step 1: Truncate message & add to history ───────────────────
        # Guard against extremely long messages that could overflow context
        MAX_MSG_CHARS = 2000
        if len(user_message) > MAX_MSG_CHARS:
            user_message = user_message[:MAX_MSG_CHARS] + "... (truncated)"

        context["history"].append({"role": "user", "content": user_message})

        # Trim history to keep only the most recent messages (prevent
        # unbounded memory growth). We keep 20 messages (10 turns) which
        # is what the LLM actually sees, plus a small buffer.
        MAX_HISTORY = 24
        if len(context["history"]) > MAX_HISTORY:
            context["history"] = context["history"][-MAX_HISTORY:]

        # ── Step 2: Rule-based emergency check (FAST safety net) ────────
        emergency_matches = check_emergency_keywords(user_message)

        # ── Step 3: Get LLM response ───────────────────────────────────
        llm_result = self.llm.generate(context, user_message)

        # ── Step 4: Extract and update symptoms ────────────────────────
        new_symptoms = llm_result.get("extracted_symptoms", [])
        if new_symptoms:
            existing = set(context["symptoms"])
            existing.update(s.lower().strip() for s in new_symptoms)
            context["symptoms"] = list(existing)

        # ── Step 5: Update severity if assessed ────────────────────────
        llm_severity = llm_result.get("severity")
        if llm_severity and llm_severity in ("critical", "moderate", "mild"):
            context["severity"] = llm_severity

        # ── Step 6: Update department if recommended ───────────────────
        llm_department = llm_result.get("recommended_department")
        if llm_department:
            context["department"] = llm_department

        # ── Step 7: Update appointment details ─────────────────────────
        collected_info = llm_result.get("collected_info", {})
        if collected_info:
            for key in ["patient_name", "preferred_date", "preferred_time", "contact_number"]:
                value = collected_info.get(key)
                if value and value.lower() not in ("null", "none", ""):
                    context["appointment"][key] = value

        # ── Step 8: Determine response and state ───────────────────────
        response = llm_result.get("response", "I apologize, something went wrong.")
        llm_intent = llm_result.get("intent", "other")

        # EMERGENCY OVERRIDE: Rule-based keywords always win
        if emergency_matches:
            context["state"] = "emergency"
            context["is_emergency"] = True
            context["severity"] = "critical"
            if not llm_result.get("is_emergency"):
                response = self._get_emergency_response(emergency_matches, context)

        # LLM-detected emergency
        elif llm_result.get("is_emergency") or llm_severity == "critical":
            context["state"] = "emergency"
            context["is_emergency"] = True
            context["severity"] = "critical"

        # ── Intent switching detection ──────────────────────────────────
        # If user switches intent mid-flow, override the state machine
        elif self._detect_intent_switch(context["state"], llm_intent):
            new_state = self._resolve_intent_switch(llm_intent)
            if new_state:
                context["state"] = new_state

        # Normal flow: use LLM's suggested state
        else:
            suggested = llm_result.get("suggested_next_state")
            if suggested and is_valid_transition(context["state"], suggested):
                context["state"] = suggested
            # If LLM suggests invalid transition, keep current state

        # ── Step 9: Handle booking confirmation ────────────────────────
        if context["state"] == "booking_confirmation":
            response, context = self._handle_booking(response, context)

        # ── Step 10: Sanitize response — NEVER show raw JSON to user ───
        response = self._sanitize_response(response)

        # ── Step 11: Add bot response to history ───────────────────────
        context["history"].append({"role": "assistant", "content": response})

        return response, context

    @staticmethod
    def _sanitize_response(response: str) -> str:
        """
        Last line of defense: if the response still looks like JSON,
        extract the natural language 'response' field or replace it.
        """
        import json

        stripped = response.strip()
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
                if isinstance(data, dict) and "response" in data:
                    return data["response"]
                # It's JSON but without a response field
                return (
                    "Thank you for sharing. Could you tell me more about "
                    "your symptoms so I can better assist you?"
                )
            except (json.JSONDecodeError, TypeError):
                pass
        return response

    # ── Intent Switching Helpers ────────────────────────────────────────

    def _detect_intent_switch(self, current_state: str, llm_intent: str) -> bool:
        """
        Detect if the user's intent conflicts with the current state.
        E.g., user is in booking flow but reports new symptoms.
        """
        # If user reports symptoms while in booking/appointment flow
        if llm_intent == "symptom_report" and current_state in (
            "collecting_details", "booking_confirmation", "appointment_offer",
        ):
            return True

        # If user requests booking while in symptom/triage flow
        if llm_intent == "booking_request" and current_state in (
            "symptom_collection", "severity_assessment",
        ):
            return True

        # If user cancels during booking
        if llm_intent == "cancellation" and current_state in (
            "collecting_details", "booking_confirmation",
        ):
            return True

        return False

    def _resolve_intent_switch(self, llm_intent: str) -> str | None:
        """Map an intent to the appropriate state when switching."""
        intent_to_state = {
            "symptom_report": "symptom_collection",
            "booking_request": "appointment_offer",
            "cancellation": "completed",
            "greeting": "greeting",
        }
        return intent_to_state.get(llm_intent)

    def get_greeting(self) -> str:
        """Return the initial greeting message."""
        return (
            "👋 **Hello! Welcome to HealthAssist.**\n\n"
            "I'm your healthcare triage assistant. I can help you:\n\n"
            "- 🔍 **Assess your symptoms** and determine their severity\n"
            "- 🏥 **Recommend the right department** for your needs\n"
            "- 📅 **Book an appointment** with the appropriate specialist\n\n"
            "⚠️ *If you're experiencing a life-threatening emergency, "
            "please call **911** or **112** immediately.*\n\n"
            "**How can I help you today?** Please describe your symptoms or concern."
        )

    def _get_emergency_response(self, keywords: list[str], context: dict) -> str:
        """Generate an emergency escalation response."""
        matched = ", ".join(keywords[:3])
        symptoms_str = ", ".join(context.get("symptoms", [])) or matched

        return (
            "🚨 **EMERGENCY ALERT** 🚨\n\n"
            f"Based on what you've described (**{symptoms_str}**), "
            "this appears to be a **critical medical emergency**.\n\n"
            "### ⚡ Immediate Actions Required:\n\n"
            "1. **Call emergency services NOW**: Dial **911** (US) or **112** (EU/India)\n"
            "2. **Do not wait** — seek immediate medical attention\n"
            "3. If someone is with you, ask them to help while you call\n\n"
            "### 🚫 Important:\n"
            "- I **cannot** book a regular appointment for emergency conditions\n"
            "- Emergency cases need **immediate in-person medical care**\n"
            "- Please go to the nearest **Emergency Room (ER)** if you can\n\n"
            "---\n"
            "*Once you are safe, feel free to start a new conversation "
            "for any non-emergency health concerns.*"
        )

    def _handle_booking(self, response: str, context: dict) -> tuple[str, dict]:
        """Handle the appointment booking step."""
        appt = context["appointment"]

        # Check if all required details are collected
        required = ["patient_name", "preferred_date", "preferred_time", "contact_number"]
        missing = [f for f in required if not appt.get(f)]

        if missing:
            # Not all details collected yet — stay in collecting_details
            context["state"] = "collecting_details"
            return response, context

        # All details present — attempt to save to MongoDB
        booking_id = self.db.save_appointment(context)

        if booking_id:
            context["state"] = "completed"
            context["booking_id"] = booking_id
            response = (
                "✅ **Appointment Confirmed!**\n\n"
                f"📋 **Booking Details:**\n\n"
                f"| Field | Details |\n"
                f"|-------|--------|\n"
                f"| 🆔 **Booking ID** | `{booking_id[-8:]}` |\n"
                f"| 👤 **Patient** | {appt['patient_name']} |\n"
                f"| 📅 **Date** | {appt['preferred_date']} |\n"
                f"| 🕐 **Time** | {appt['preferred_time']} |\n"
                f"| 📞 **Contact** | {appt['contact_number']} |\n"
                f"| 🏥 **Department** | {context.get('department', 'General Medicine')} |\n"
                f"| ⚖️ **Severity** | {context.get('severity', 'N/A').title()} |\n\n"
                "Your appointment has been saved. "
                "Please arrive **15 minutes early** and bring any relevant medical documents.\n\n"
                "Is there anything else I can help you with?"
            )
        else:
            context["state"] = "completed"
            response = (
                "⚠️ **Appointment Details Recorded** (Database temporarily unavailable)\n\n"
                f"📋 **Your Details:**\n\n"
                f"| Field | Details |\n"
                f"|-------|--------|\n"
                f"| 👤 **Patient** | {appt['patient_name']} |\n"
                f"| 📅 **Date** | {appt['preferred_date']} |\n"
                f"| 🕐 **Time** | {appt['preferred_time']} |\n"
                f"| 📞 **Contact** | {appt['contact_number']} |\n"
                f"| 🏥 **Department** | {context.get('department', 'General Medicine')} |\n\n"
                "Please call the hospital directly to confirm your appointment.\n\n"
                "Is there anything else I can help you with?"
            )

        return response, context

    def get_status_displays(self, context: dict) -> dict:
        """Generate formatted status information for the Gradio sidebar."""
        state = context.get("state", "greeting")
        symptoms = context.get("symptoms", [])
        severity = context.get("severity")
        department = context.get("department")
        appointment = context.get("appointment", {})
        booking_id = context.get("booking_id")

        # State label
        state_md = STATE_LABELS.get(state, state)

        # Symptoms
        if symptoms:
            symptoms_md = "\n".join(f"• {s.title()}" for s in symptoms)
        else:
            symptoms_md = "*No symptoms recorded yet*"

        # Severity with color
        severity_map = {
            "critical": "🔴 **CRITICAL**",
            "moderate": "🟡 **Moderate**",
            "mild": "🟢 **Mild**",
        }
        severity_md = severity_map.get(severity, "⚪ *Not assessed*")

        # Department
        department_md = f"🏥 **{department}**" if department else "*Not determined*"

        # Appointment
        appt_lines = []
        if appointment.get("patient_name"):
            appt_lines.append(f"👤 {appointment['patient_name']}")
        if appointment.get("preferred_date"):
            appt_lines.append(f"📅 {appointment['preferred_date']}")
        if appointment.get("preferred_time"):
            appt_lines.append(f"🕐 {appointment['preferred_time']}")
        if appointment.get("contact_number"):
            appt_lines.append(f"📞 {appointment['contact_number']}")
        if booking_id:
            appt_lines.append(f"🆔 `{booking_id[-8:]}`")

        appointment_md = "\n".join(appt_lines) if appt_lines else "*No appointment*"

        return {
            "status": state_md,
            "symptoms": symptoms_md,
            "severity": severity_md,
            "department": department_md,
            "appointment": appointment_md,
        }
