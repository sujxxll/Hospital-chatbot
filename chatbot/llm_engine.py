"""
LLM Engine — Google Gemini Integration (google.genai SDK).

Handles all communication with the Gemini API, including:
  - System prompt construction with conversation context
  - Structured JSON response generation
  - Response parsing with fallback handling
"""

import json
import re
from google import genai
from google.genai import types
from chatbot.medical_knowledge import get_department_info
import config


# ── System Prompt ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a professional healthcare triage assistant for a hospital system.
Your name is "HealthAssist". You are empathetic, professional, and thorough.

## YOUR ROLE
1. Understand patient symptoms through caring, multi-turn conversation
2. Ask clarifying follow-up questions when symptoms are vague or incomplete
3. Assess the severity of their condition (Critical, Moderate, or Mild)
4. Recommend the appropriate hospital department
5. Help book appointments for NON-CRITICAL cases only

## CRITICAL SAFETY RULES (NEVER VIOLATE)
- You are NOT a doctor. NEVER diagnose conditions or prescribe treatments.
- For CRITICAL/EMERGENCY cases: IMMEDIATELY advise calling emergency services (911/112).
  Do NOT continue the booking flow for critical cases.
- Always err on the side of caution — if unsure, classify as higher severity.
- If the user mentions chest pain, difficulty breathing, loss of consciousness,
  severe bleeding, stroke symptoms, seizures, poisoning, or suicidal thoughts,
  treat it as a CRITICAL emergency.

## CONVERSATION FLOW
1. Greet the user warmly and ask about their health concern
2. Extract and clarify symptoms (ask follow-up questions as needed)
3. Assess severity (Critical → emergency escalation, Moderate/Mild → continue)
4. Recommend appropriate department and explain why
5. Offer to book an appointment
6. Collect appointment details: patient name, preferred date, preferred time, contact number
7. Confirm the appointment details

## INTENT SWITCHING
- If a user switches intent mid-conversation (e.g., mentions emergency symptoms while booking),
  you MUST immediately switch to triage/emergency mode.
- After handling the new intent, you may offer to resume the previous flow if appropriate.

## AVAILABLE DEPARTMENTS
{departments}

## RESPONSE FORMAT
You MUST respond with ONLY a valid JSON object (no markdown, no extra text). Schema:
{{
  "response": "Your natural, empathetic message to the user (use markdown formatting for readability)",
  "extracted_symptoms": ["symptom1", "symptom2"],
  "severity": "critical" | "moderate" | "mild" | null,
  "is_emergency": true | false,
  "recommended_department": "Department Name" | null,
  "intent": "greeting" | "symptom_report" | "clarification_response" | "booking_request" | "providing_details" | "confirmation" | "cancellation" | "other",
  "needs_clarification": true | false,
  "collected_info": {{
    "patient_name": "extracted name or null",
    "preferred_date": "extracted date or null",
    "preferred_time": "extracted time or null",
    "contact_number": "extracted number or null"
  }},
  "suggested_next_state": "greeting" | "symptom_collection" | "severity_assessment" | "emergency" | "department_recommendation" | "appointment_offer" | "collecting_details" | "booking_confirmation" | "completed"
}}
""".format(departments=get_department_info())


# ── Context Prompt Builder ─────────────────────────────────────────────────

def build_context_prompt(context: dict, user_message: str) -> str:
    """Build a context-aware prompt for the current conversation turn."""

    state = context.get("state", "greeting")
    symptoms = context.get("symptoms", [])
    severity = context.get("severity")
    department = context.get("department")
    appointment = context.get("appointment", {})
    history = context.get("history", [])

    # Build conversation history string
    history_str = ""
    for msg in history[-10:]:      # Last 10 messages for context window
        role = "Patient" if msg["role"] == "user" else "HealthAssist"
        history_str += f"{role}: {msg['content']}\n"

    # Determine what appointment info is still needed
    missing_fields = []
    appt_fields = {
        "patient_name": "Patient Name",
        "preferred_date": "Preferred Date",
        "preferred_time": "Preferred Time",
        "contact_number": "Contact Number",
    }
    for key, label in appt_fields.items():
        if not appointment.get(key):
            missing_fields.append(label)

    collected_str = ", ".join(
        f"{label}: {appointment.get(key, 'Not provided')}"
        for key, label in appt_fields.items()
        if appointment.get(key)
    ) or "None yet"

    prompt = f"""## CURRENT CONVERSATION CONTEXT
- **Current State**: {state}
- **Collected Symptoms**: {', '.join(symptoms) if symptoms else 'None yet'}
- **Severity Assessment**: {severity or 'Not assessed yet'}
- **Recommended Department**: {department or 'Not determined yet'}
- **Appointment Info Collected**: {collected_str}
- **Still Needed**: {', '.join(missing_fields) if missing_fields else 'All info collected'}

## CONVERSATION HISTORY
{history_str if history_str else '(This is the start of the conversation)'}

## LATEST PATIENT MESSAGE
Patient: {user_message}

## YOUR TASK
Based on the current state and conversation context, respond appropriately.
- If state is "greeting": Welcome the user and ask about their health concern.
- If state is "symptom_collection": Extract symptoms, ask clarifying questions if needed.
- If state is "severity_assessment": Classify severity and proceed accordingly.
- If state is "department_recommendation": Recommend a department and explain why.
- If state is "appointment_offer": Ask if they'd like to book an appointment.
- If state is "collecting_details": Ask for the NEXT missing piece of appointment info.
- If state is "booking_confirmation": Summarize all details and ask for confirmation.
- If state is "emergency": Advise calling emergency services IMMEDIATELY.
- If state is "completed": Confirm booking and offer further help.

Respond with ONLY a valid JSON object."""

    return prompt


class LLMEngine:
    """Handles all interactions with the Google Gemini LLM."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        self.api_key = api_key or config.GOOGLE_API_KEY
        self.model_name = model_name or config.GEMINI_MODEL

        if not self.api_key:
            raise ValueError(
                "Google API key is required. Set GOOGLE_API_KEY in your .env file.\n"
                "Get a key at: https://aistudio.google.com/apikey"
            )

        self.client = genai.Client(api_key=self.api_key)

    def generate(self, context: dict, user_message: str) -> dict:
        """
        Generate a structured response from the LLM.

        Args:
            context: Current conversation context dictionary.
            user_message: The latest user message.

        Returns:
            Parsed JSON dict with response, symptoms, severity, etc.
        """
        prompt = build_context_prompt(context, user_message)

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=config.TEMPERATURE,
                    top_p=config.TOP_P,
                    max_output_tokens=config.MAX_OUTPUT_TOKENS,
                    response_mime_type="application/json",
                ),
            )
            return self._parse_response(response.text)
        except Exception as e:
            print(f"[LLM ERROR] {e}")
            return self._fallback_response(str(e))

    def _parse_response(self, raw_text: str) -> dict:
        """Parse the LLM's JSON response, with fallback handling."""
        parsed = None

        # Attempt 1: Direct JSON parse
        try:
            parsed = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError):
            pass

        # Attempt 2: Extract from markdown code blocks
        if parsed is None:
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

        # Attempt 3: Find any JSON object in the text
        if parsed is None:
            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

        # If parsing succeeded, validate and return
        if parsed and isinstance(parsed, dict):
            return self._validate_parsed_result(parsed)

        # All parsing failed — return safe fallback (NEVER show raw JSON to user)
        print(f"[LLM PARSE WARNING] Could not parse JSON: {raw_text[:200]}")
        return self._fallback_response("JSON parse failure")

    def _validate_parsed_result(self, parsed: dict) -> dict:
        """
        Ensure the parsed LLM result has a valid, user-friendly 'response' field.
        This prevents raw JSON from ever being shown to the user.
        """
        response_text = parsed.get("response", "")

        # Guard: If 'response' is missing, empty, or still looks like JSON
        if not response_text or self._looks_like_json(response_text):
            # Try to build a reasonable response from the other fields
            dept = parsed.get("recommended_department", "")
            severity = parsed.get("severity", "")
            symptoms = parsed.get("extracted_symptoms", [])

            if parsed.get("is_emergency"):
                parsed["response"] = (
                    "🚨 **This appears to be a medical emergency.** "
                    "Please call **911** or **112** immediately for urgent care."
                )
            elif dept:
                symptom_str = ", ".join(symptoms) if symptoms else "your symptoms"
                parsed["response"] = (
                    f"Based on {symptom_str}, I recommend visiting **{dept}**. "
                    f"Assessed severity: **{severity or 'under review'}**. "
                    "Would you like to book an appointment?"
                )
            else:
                parsed["response"] = (
                    "Thank you for sharing. Could you tell me more about "
                    "your symptoms so I can better assist you?"
                )

        # Ensure all expected keys exist with safe defaults
        defaults = {
            "extracted_symptoms": [],
            "severity": None,
            "is_emergency": False,
            "recommended_department": None,
            "intent": "other",
            "needs_clarification": False,
            "collected_info": {},
            "suggested_next_state": None,
        }
        for key, default_val in defaults.items():
            if key not in parsed:
                parsed[key] = default_val

        return parsed

    @staticmethod
    def _looks_like_json(text: str) -> bool:
        """Check if a string looks like raw JSON (should never be shown to user)."""
        stripped = text.strip()
        # Starts with { or [ — likely JSON
        if stripped.startswith(("{", "[")):
            try:
                json.loads(stripped)
                return True
            except (json.JSONDecodeError, TypeError):
                pass
        # Contains multiple JSON-like keys — likely leaked JSON
        json_patterns = ['"response":', '"severity":', '"extracted_symptoms":',
                         '"is_emergency":', '"suggested_next_state":']
        matches = sum(1 for p in json_patterns if p in stripped)
        return matches >= 2

    def _fallback_response(self, error_msg: str) -> dict:
        """Return a safe fallback response when the LLM fails."""
        return {
            "response": (
                "I apologize, but I'm experiencing a technical issue right now. "
                "If you're experiencing a medical emergency, please call **911** or **112** immediately.\n\n"
                "Please try again in a moment."
            ),
            "extracted_symptoms": [],
            "severity": None,
            "is_emergency": False,
            "recommended_department": None,
            "intent": "other",
            "needs_clarification": False,
            "collected_info": {},
            "suggested_next_state": None,
        }
