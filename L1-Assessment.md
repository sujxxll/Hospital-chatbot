# AI/ML Engineer - L1 Interview

**DURATION:** 70 MINS

## Healthcare Conversational Triage and Appointment System

### Problem Statement

Design and implement a conversational healthcare assistant for a hospital system. The assistant must engage in multi-turn dialogue with patients, understand their medical concerns, assess the severity of their condition, recommend the appropriate hospital department, and book an appointment if required. The system must also detect critical emergency cases and escalate them immediately.

The assistant should not immediately book appointments. Instead, it must first analyze the user's health problem, ask relevant follow-up questions when necessary, and determine the appropriate next step.

### Functional Expectations

1. **Symptom Understanding**: The assistant should begin by identifying and extracting the user's symptoms. It must handle natural, free-form inputs such as:
   - "I have chest pain."
   - "My child has high fever and vomiting."
   - "I feel dizziness and blurred vision."
   
   The system should ask clarifying questions if required to better understand the condition.

2. **Severity Assessment**: Based on the collected information, the system must classify the case as critical, moderate, or mild. Critical conditions must trigger immediate escalation. The normal booking flow must not continue in such cases.

3. **Department Recommendation**: Based on symptoms and severity, the assistant must determine the appropriate hospital department and explain the recommendation before proceeding.

4. **Appointment Booking**: If the condition requires consultation and the user agrees, the assistant should collect necessary details (such as name, preferred date and time, and contact information) and confirm the appointment.

5. **Conversational Behaviour**: The system must support multi-turn interactions, maintain context across turns, handle interruptions and intent switching, and resume previous flow when appropriate.
   - *Example scenario*: User: "I want to book an appointment." Assistant: "What issue are you experiencing?" User: "Actually I have chest pain." -> The assistant should switch to triage mode rather than directly booking.

### Technical Scope

You may use publicly available datasets for medical knowledge or symptom mapping if required. However, you are expected to design the conversational logic, triage mechanism, and safety controls independently.

Your solution should demonstrate:
- Clear system design
- Thoughtful handling of medical risk
- Explicit emergency detection
- Proper conversational state management
- Safe and structured response generation

### Deliverables

Provide:
- A high-level system design
- Explanation of your triage and routing logic
- Description of severity classification method
- Explanation of how emergencies are detected and handled
- A minimal working prototype or structured implementation outline
