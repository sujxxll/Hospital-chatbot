# 🏥 Healthcare Conversational Triage & Appointment System

## Complete End-to-End System Design & Flow

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GRADIO UI (Frontend)                        │
│  ┌──────────────────────┐     ┌──────────────────────────────────┐  │
│  │   Chat Interface     │     │   Triage Status Sidebar          │  │
│  │   • Multi-turn chat  │     │   • Phase indicator              │  │
│  │   • Message input    │     │   • Symptoms list                │  │
│  │   • Example prompts  │     │   • Severity badge (🔴🟡🟢)      │  │
│  │                      │     │   • Department recommendation    │  │
│  │                      │     │   • Appointment details          │  │
│  └──────────┬───────────┘     └──────────────────────────────────┘  │
└─────────────┼──────────────────────────────────────────────────────┘
              │ User Message
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CONVERSATION MANAGER (Orchestrator)               │
│                                                                     │
│  ┌─────────────────┐   ┌───────────────┐   ┌────────────────────┐  │
│  │ 1. EMERGENCY    │   │ 2. LLM ENGINE │   │ 3. STATE MACHINE   │  │
│  │    KEYWORD SCAN │   │    (Gemini    │   │    (9 States)      │  │
│  │    (Rule-based) │──▶│    2.5 Flash) │──▶│    + Transitions   │  │
│  │    FAST Safety  │   │    Structured │   │    + Validation    │  │
│  │    Net          │   │    JSON Output│   │    + Intent Switch │  │
│  └─────────────────┘   └───────────────┘   └────────────────────┘  │
│                                                                     │  
│  ┌─────────────────┐   ┌───────────────────────────────────────┐   │
│  │ 4. MEDICAL KB   │   │ 5. CONTEXT MANAGER                   │   │
│  │ • 14 Departments│   │ • History trimming (24 msgs max)     │   │
│  │ • Emergency     │   │ • Turn limit (50 turns max)          │   │
│  │   keywords      │   │ • Message truncation (2000 chars)    │   │
│  │ • Symptom maps  │   │ • Sliding window (last 10 to LLM)   │   │
│  └─────────────────┘   └───────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
              │ Appointment Data
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     MONGODB (Persistence Layer)                     │
│  Database: hospital_colab_chatbot                                   │
│  Collection: appointments                                           │
│  Schema: { patient_name, contact, date, time, department,           │
│            symptoms[], severity, status, timestamp, summary }       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Project Structure

```
Hospital-chatbot/
├── app.py                              # Gradio UI — entry point
├── config.py                           # Centralized configuration
├── requirements.txt                    # Dependencies
├── .env                                # API keys & MongoDB URI
├── L1-Assessment.md                    # Original assessment
├── SYSTEM_DESIGN.md                    # This document
│
├── chatbot/                            # Core chatbot engine
│   ├── __init__.py
│   ├── states.py                       # State machine (9 states + transitions)
│   ├── medical_knowledge.py            # Medical KB, emergency keywords, departments
│   ├── llm_engine.py                   # Gemini 2.5 Flash integration
│   └── conversation_manager.py         # Orchestrator — ties everything together
│
└── database/                           # Persistence layer
    ├── __init__.py
    └── mongo_client.py                 # MongoDB CRUD for appointments
```

---

## 3. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Frontend** | Gradio 6.x | Rapid prototyping, built-in chat components, real-time updates |
| **LLM** | Google Gemini 2.5 Flash | Fast inference, structured JSON output, low cost |
| **Backend** | Python 3.11+ | Rich ecosystem, LLM library support |
| **Database** | MongoDB | Flexible schema for appointment records, easy to scale |
| **Config** | python-dotenv | Secure credential management |

---

## 4. Conversation Flow (End-to-End)

### 4.1 Normal Flow (Mild/Moderate Case)

```
User: "I have a headache and mild nausea"
                │
                ▼
┌──────────────────────────────┐
│  STATE: GREETING → SYMPTOM   │
│  COLLECTION                  │
│                              │
│  Bot: "Can you tell me more? │
│  How long? How severe?"      │
└──────────┬───────────────────┘
           │
           ▼
User: "It's been 2 days, moderate pain"
                │
                ▼
┌──────────────────────────────┐
│  STATE: SEVERITY_ASSESSMENT  │
│                              │
│  Severity: 🟡 MODERATE       │
│  Symptoms: [headache, nausea]│
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  STATE: DEPARTMENT_           │
│  RECOMMENDATION              │
│                              │
│  Bot: "I recommend Neurology │
│  for your symptoms."         │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  STATE: APPOINTMENT_OFFER    │
│                              │
│  Bot: "Would you like to     │
│  book an appointment?"       │
└──────────┬───────────────────┘
           │ User: "Yes"
           ▼
┌──────────────────────────────┐
│  STATE: COLLECTING_DETAILS   │
│                              │
│  Collect: Name → Date →      │
│  Time → Contact Number       │
└──────────┬───────────────────┘
           │ All 4 fields collected
           ▼
┌──────────────────────────────┐
│  STATE: BOOKING_CONFIRMATION │
│                              │
│  Bot: "Please confirm your   │
│  appointment details..."     │
│                              │
│  → Save to MongoDB ✅        │
│  → Generate Booking ID       │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  STATE: COMPLETED            │
│                              │
│  Bot: "Appointment confirmed!│
│  Booking ID: abc12345"       │
└──────────────────────────────┘
```

### 4.2 Emergency Flow (Critical Case)

```
User: "I have severe chest pain and can't breathe"
                │
                ▼
┌──────────────────────────────────────────────────┐
│  LAYER 1: Rule-Based Emergency Keyword Scan      │
│  ⚡ INSTANT — runs BEFORE the LLM                │
│                                                  │
│  Matched: "chest pain", "can't breathe"          │
│  → IMMEDIATE escalation, no LLM needed           │
└──────────┬───────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────┐
│  LAYER 2: LLM Analysis (confirms)               │
│  severity: "critical", is_emergency: true        │
│  department: "Emergency Medicine"                │
└──────────┬───────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────┐
│  STATE: EMERGENCY                                │
│                                                  │
│  🚨 EMERGENCY ALERT 🚨                           │
│  "Call 911/112 immediately!"                     │
│  Booking flow is BLOCKED for safety              │
│  No appointment is created                       │
└──────────────────────────────────────────────────┘
```

### 4.3 Intent Switching Flow

```
User: "I want to book an appointment"
   → STATE: SYMPTOM_COLLECTION
   → Bot: "What symptoms are you experiencing?"

User: "Actually I have chest pain"
   → Emergency keyword detected! ⚡
   → STATE: EMERGENCY (overrides booking flow)
   → Bot: "🚨 Call emergency services immediately!"

--- OR ---

User is in COLLECTING_DETAILS (giving name, date, etc.)
User: "Wait, I also feel dizzy and nauseous"
   → Intent detected: symptom_report (conflicts with collecting_details)
   → STATE switches: COLLECTING_DETAILS → SYMPTOM_COLLECTION
   → Bot processes new symptoms first, then may resume booking
```

---

## 5. Dual-Layer Emergency Detection

This is the **most critical safety feature** of the system.

```
User Input
    │
    ├──▶ LAYER 1: Rule-Based Keyword Scan (FAST, 0ms)
    │    • 60+ emergency keywords across 8 categories
    │    • Categories: cardiac, respiratory, neurological,
    │      bleeding, trauma, toxicology, allergic, mental_health
    │    • Runs BEFORE the LLM — can't be bypassed
    │    • If matched → IMMEDIATE emergency escalation
    │
    └──▶ LAYER 2: LLM Analysis (NUANCED, ~1-2s)
         • Understands context and severity from free-form text
         • Can detect emergencies that keywords miss
         • Returns: is_emergency: true/false, severity: critical
         • If detected → Emergency escalation

    EITHER layer detecting emergency → System escalates
    Booking flow is BLOCKED for all critical cases
```

**Why dual-layer?**
- **Keywords alone** would miss: "my vision suddenly went black on one side" (stroke symptom)
- **LLM alone** could hallucinate or misclassify — the keyword layer is a deterministic safety net
- Together they provide **defense in depth** for patient safety

---

## 6. Severity Classification

| Level | Criteria | Action | Example |
|-------|----------|--------|---------|
| 🔴 **Critical** | Life-threatening, any emergency keyword match, LLM classifies as critical | Immediate escalation, booking BLOCKED | Chest pain, seizure, severe bleeding |
| 🟡 **Moderate** | Needs medical attention but not immediately life-threatening | Recommend department, offer appointment | Persistent fever, recurring headache, blood in stool |
| 🟢 **Mild** | Minor discomfort, can wait for scheduled visit | Recommend department, offer appointment | Mild backache, common cold, minor skin rash |

---

## 7. State Machine Design

### 9 States with Validated Transitions

```
GREETING ──────────▶ SYMPTOM_COLLECTION ──────▶ SEVERITY_ASSESSMENT
    │                    │    ▲                        │
    │                    │    │ (need more info)        │
    │                    ▼    │                        ▼
    │              ┌─────────────┐            ┌───────────────┐
    └─────────────▶│  EMERGENCY  │◀───────────│  DEPT_RECOM   │
     (any state)   │  (blocked)  │            └───────┬───────┘
                   └─────────────┘                    │
                                                      ▼
                                              APPOINTMENT_OFFER
                                                      │
                                                      ▼
                                              COLLECTING_DETAILS
                                                      │
                                                      ▼
                                            BOOKING_CONFIRMATION
                                                      │
                                                      ▼
                                                 COMPLETED
```

**Key safety rule:** EMERGENCY is reachable from **ANY** state — it overrides everything.

---

## 8. Triage & Department Routing Logic

### How it works:
1. **LLM extracts symptoms** from natural language input
2. **Medical Knowledge Base** maps symptoms → possible departments (14 departments)
3. **LLM selects the best department** based on full symptom + context analysis
4. **Pediatrics indicator**: If child/kid/baby mentioned, routes to Pediatrics

### Department Coverage (14 Departments):
| Department | Example Symptoms |
|-----------|-----------------|
| Cardiology | Chest pain, palpitations, high blood pressure |
| Neurology | Headache, dizziness, numbness, blurred vision |
| Orthopedics | Joint pain, back pain, fractures |
| Gastroenterology | Stomach pain, nausea, vomiting, diarrhea |
| Pulmonology | Cough, breathing difficulty, asthma |
| Dermatology | Skin rash, itching, eczema |
| ENT | Ear pain, sore throat, sinus |
| Ophthalmology | Eye pain, blurred vision, vision loss |
| Pediatrics | Child fever, child rash, child cough |
| Psychiatry | Anxiety, depression, insomnia |
| General Medicine | Fever, fatigue, cold, flu |
| Urology | Painful urination, kidney pain |
| Gynecology | Pelvic pain, menstrual issues |
| Emergency Medicine | Severe trauma, unresponsive fever |

---

## 9. Context & Conversation Management

### Problem: Context Window Overflow
Long conversations can exceed the LLM's context window, causing errors or poor responses.

### Solution: Multi-Layer Protection

| Protection | How | Value |
|-----------|-----|-------|
| **History Sliding Window** | Only last 10 messages (5 turns) sent to LLM | Keeps prompt size manageable |
| **History Trimming** | In-memory history capped at 24 messages | Prevents unbounded memory growth |
| **Message Truncation** | Individual messages capped at 2,000 characters | Prevents single-message overflow |
| **Turn Limit** | Max 50 user turns per conversation | Graceful conversation end |

### Context Passed to LLM Each Turn:
```
• Current State (e.g., "collecting_details")
• All collected symptoms
• Severity assessment
• Recommended department
• Appointment details collected so far
• Missing appointment fields
• Last 10 messages of conversation history
```

---

## 10. MongoDB Appointment Schema

```json
{
  "_id": ObjectId("..."),
  "patient_name": "John Doe",
  "contact_number": "9876543210",
  "preferred_date": "2026-03-05",
  "preferred_time": "10:30 AM",
  "department": "Neurology",
  "symptoms": ["headache", "blurred vision"],
  "severity": "moderate",
  "status": "confirmed",
  "booking_timestamp": ISODate("2026-02-28T06:30:00Z"),
  "conversation_summary": "Patient reported: headache, blurred vision. Assessed severity: moderate. Routed to: Neurology."
}
```

**Graceful fallback:** If MongoDB is unavailable, the chatbot still works — it shows appointment details to the user and asks them to call the hospital to confirm.

---

## 11. LLM Integration (Gemini 2.5 Flash)

### Structured Output
Every LLM response is forced to return **JSON** with this schema:

```json
{
  "response": "Natural language response to show the user",
  "extracted_symptoms": ["symptom1", "symptom2"],
  "severity": "critical | moderate | mild | null",
  "is_emergency": true | false,
  "recommended_department": "Department Name | null",
  "intent": "symptom_report | booking_request | greeting | ...",
  "needs_clarification": true | false,
  "collected_info": {
    "patient_name": "...",
    "preferred_date": "...",
    "preferred_time": "...",
    "contact_number": "..."
  },
  "suggested_next_state": "symptom_collection | emergency | ..."
}
```

### Why structured output?
- **Deterministic data extraction** — symptoms, severity, department are always parseable
- **State machine integration** — the LLM suggests state transitions, but the state machine validates them
- **Separation of concerns** — natural language response is separate from structured data

### Safety Settings:
- **Temperature: 0.3** — Low randomness for consistent medical triage
- **response_mime_type: "application/json"** — Forces JSON output format
- **Multi-layer JSON parsing** — Direct parse → Markdown extraction → Regex fallback

---

## 12. How to Run

### Prerequisites
- Python 3.11+
- MongoDB (local or Atlas)
- Google Gemini API key

### Setup & Launch
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API key and MongoDB URI

# 3. Run the application
python app.py

# 4. Open in browser
# http://localhost:8000
```

---

## 13. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Dual-layer emergency detection** | Patient safety cannot rely on a single point of failure |
| **State machine + LLM hybrid** | LLM handles natural language; state machine enforces safe transitions |
| **JSON structured output** | Reliable data extraction from every response |
| **Low temperature (0.3)** | Medical triage needs consistency, not creativity |
| **Stateless conversation manager** | Compatible with Gradio's session management (gr.State) |
| **MongoDB graceful fallback** | App works even without database — prioritizes availability |
| **Intent switching detection** | Required by assessment — user can change mind mid-conversation |
| **History sliding window** | Prevents context overflow while maintaining recent context |

---

## 14. Demo Scenarios

### Scenario 1: Mild Case → Full Booking
```
User: "I've had a mild cough for a few days"
Bot: Asks clarifying questions → Severity: Mild → Dept: Pulmonology
     → Offers appointment → Collects details → Confirms → Saves to MongoDB
```

### Scenario 2: Emergency Escalation
```
User: "I have severe chest pain and difficulty breathing"
Bot: 🚨 EMERGENCY → Advises calling 911 → Booking BLOCKED
```

### Scenario 3: Intent Switching
```
User: "I want to book an appointment"
Bot: "What symptoms are you experiencing?"
User: "Actually I have chest pain"
Bot: 🚨 Switches to emergency mode immediately
```

### Scenario 4: Multi-Turn Clarification
```
User: "I feel dizzy"
Bot: "How long? Any other symptoms? When does it occur?"
User: "Since yesterday, also blurred vision"
Bot: Assesses as moderate/critical → Routes to Neurology or Emergency
```

---

## 15. Summary

This system demonstrates:

✅ **Clear system design** — Modular architecture with separation of concerns  
✅ **Thoughtful handling of medical risk** — Dual-layer emergency detection, erring on caution  
✅ **Explicit emergency detection** — Rule-based keywords + LLM analysis, booking blocked for critical  
✅ **Proper conversational state management** — 9-state machine with validated transitions  
✅ **Safe and structured response generation** — JSON schema, low temperature, fallback handling  
✅ **Intent switching** — Detects mid-conversation intent changes and handles gracefully  
✅ **Context management** — Sliding window, history trimming, turn limits  
✅ **Persistent storage** — MongoDB for appointment records with graceful fallback  
