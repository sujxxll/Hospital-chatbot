"""
Healthcare Triage Assistant — Gradio Application.

A conversational healthcare chatbot with:
  - Multi-turn symptom assessment
  - Severity classification (Critical / Moderate / Mild)
  - Department recommendation
  - Appointment booking (MongoDB)
  - Real-time triage status panel
  - Emergency detection & escalation
"""

import gradio as gr
from chatbot.llm_engine import LLMEngine
from chatbot.conversation_manager import ConversationManager, create_initial_context
from database.mongo_client import MongoDBClient
import config

# ── Custom CSS ─────────────────────────────────────────────────────────────

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Global */
.gradio-container {
    font-family: 'Inter', sans-serif !important;
    max-width: 1400px !important;
}

/* Header */
.header-banner {
    background: linear-gradient(135deg, #0f766e 0%, #0d9488 30%, #14b8a6 60%, #2dd4bf 100%);
    padding: 28px 36px;
    border-radius: 16px;
    margin-bottom: 20px;
    color: white;
    box-shadow: 0 8px 32px rgba(15, 118, 110, 0.3);
    position: relative;
    overflow: hidden;
}

.header-banner::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
    border-radius: 50%;
}

.header-banner h1 {
    margin: 0 0 6px 0;
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.5px;
}

.header-banner p {
    margin: 0;
    font-size: 14px;
    opacity: 0.9;
    font-weight: 300;
}

/* Sidebar */
.status-panel {
    background: linear-gradient(180deg, #f0fdfa 0%, #f0fdf4 100%);
    border: 1px solid #99f6e4;
    border-radius: 14px;
    padding: 20px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.status-panel h3 {
    color: #0f766e;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
    font-weight: 600;
}

/* Emergency styling */
.emergency-alert {
    background: linear-gradient(135deg, #fef2f2, #fee2e2) !important;
    border: 2px solid #fca5a5 !important;
    border-radius: 12px !important;
    animation: pulse-border 2s infinite;
}

@keyframes pulse-border {
    0%, 100% { border-color: #fca5a5; }
    50% { border-color: #ef4444; }
}

/* Send button */
.send-btn {
    background: linear-gradient(135deg, #0f766e, #14b8a6) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    transition: all 0.3s ease !important;
    min-height: 45px !important;
}

.send-btn:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(15, 118, 110, 0.4) !important;
}

/* Reset button */
.reset-btn {
    background: white !important;
    border: 2px solid #e5e7eb !important;
    color: #6b7280 !important;
    font-weight: 500 !important;
    border-radius: 12px !important;
    transition: all 0.3s ease !important;
}

.reset-btn:hover {
    border-color: #0d9488 !important;
    color: #0d9488 !important;
}

/* Footer */
.footer-note {
    text-align: center;
    font-size: 12px;
    color: #9ca3af;
    margin-top: 12px;
    padding: 8px;
}
"""


# ── Initialize Core Components ─────────────────────────────────────────────

def initialize_components():
    """Initialize the LLM engine and database client."""
    try:
        llm = LLMEngine()
    except ValueError as e:
        print(f"[INIT ERROR] {e}")
        llm = None

    db = MongoDBClient()
    return llm, db


# ── Build Gradio App ───────────────────────────────────────────────────────

def create_app():
    """Build and return the Gradio application."""

    llm_engine, db_client = initialize_components()

    if llm_engine:
        manager = ConversationManager(llm_engine, db_client)
    else:
        manager = None

    # ── Event Handlers ─────────────────────────────────────────────────

    def respond(message, chat_history, context):
        """Process user message and return updated state."""
        if not message or not message.strip():
            return chat_history, context, "", "", "", "", "", ""

        if manager is None:
            error_msg = (
                "⚠️ **Setup Required**: Please set your `GOOGLE_API_KEY` in the `.env` file.\n\n"
                "1. Copy `.env.example` to `.env`\n"
                "2. Add your Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)\n"
                "3. Restart the application"
            )
            chat_history.append({"role": "user", "content": message})
            chat_history.append({"role": "assistant", "content": error_msg})
            return chat_history, context, "⚠️ Setup Required", "", "", "", "", ""

        # Process the message
        bot_response, context = manager.process_message(message, context)

        # Update chat history
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": bot_response})

        # Get status displays
        status = manager.get_status_displays(context)

        return (
            chat_history,
            context,
            status["status"],
            status["symptoms"],
            status["severity"],
            status["department"],
            status["appointment"],
            "",  # Clear input textbox
        )

    def reset_conversation():
        """Reset the conversation to initial state."""
        ctx = create_initial_context()
        greeting = manager.get_greeting() if manager else "⚠️ Please configure your API key."
        history = [{"role": "assistant", "content": greeting}]

        return (
            history,
            ctx,
            "👋 Welcome",
            "*No symptoms recorded yet*",
            "⚪ *Not assessed*",
            "*Not determined*",
            "*No appointment*",
        )

    # ── Build UI ───────────────────────────────────────────────────────

    with gr.Blocks(
        css=CUSTOM_CSS,
        title="HealthAssist — Healthcare Triage Assistant",
        theme=gr.themes.Soft(
            primary_hue=gr.themes.colors.teal,
            secondary_hue=gr.themes.colors.emerald,
            neutral_hue=gr.themes.colors.gray,
            font=gr.themes.GoogleFont("Inter"),
        ),
    ) as app:

        # State
        conv_context = gr.State(create_initial_context())

        # ── Header ─────────────────────────────────────────────────────
        gr.HTML("""
        <div class="header-banner">
            <h1>🏥 HealthAssist — Healthcare Triage Assistant</h1>
            <p>
                AI-powered symptom assessment • Severity classification • Department routing • Appointment booking
            </p>
        </div>
        """)

        with gr.Row():

            # ── Main Chat Column ───────────────────────────────────────
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    value=[{
                        "role": "assistant",
                        "content": manager.get_greeting() if manager else "⚠️ Please configure your API key in `.env`.",
                    }],
                    height=520,
                )

                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="Describe your symptoms or health concern...",
                        show_label=False,
                        scale=5,
                        container=False,
                        autofocus=True,
                    )
                    send_btn = gr.Button(
                        "Send ➤",
                        variant="primary",
                        scale=1,
                        elem_classes=["send-btn"],
                        min_width=100,
                    )

                with gr.Row():
                    clear_btn = gr.Button(
                        "🔄 New Conversation",
                        variant="secondary",
                        elem_classes=["reset-btn"],
                        size="sm",
                    )

                gr.Examples(
                    examples=[
                        "I have a severe headache and blurred vision",
                        "My child has high fever and vomiting since morning",
                        "I feel some mild back pain that comes and goes",
                        "I want to book an appointment for a routine checkup",
                        "I have chest pain and difficulty breathing",
                    ],
                    inputs=msg,
                    label="💡 Try these examples:",
                    examples_per_page=5,
                )

            # ── Sidebar: Triage Status Panel ───────────────────────────
            with gr.Column(scale=1, min_width=280):
                with gr.Group(elem_classes=["status-panel"]):
                    gr.HTML("<h3>📊 Phase</h3>")
                    status_display = gr.Markdown("👋 Welcome")

                    gr.HTML("<h3>🩺 Symptoms</h3>")
                    symptoms_display = gr.Markdown("*No symptoms recorded yet*")

                    gr.HTML("<h3>⚖️ Severity</h3>")
                    severity_display = gr.Markdown("⚪ *Not assessed*")

                    gr.HTML("<h3>🏥 Department</h3>")
                    department_display = gr.Markdown("*Not determined*")

                    gr.HTML("<h3>📅 Appointment</h3>")
                    appointment_display = gr.Markdown("*No appointment*")

        # ── Footer ─────────────────────────────────────────────────────
        gr.HTML("""
        <div class="footer-note">
            ⚠️ <strong>Disclaimer:</strong> HealthAssist is an AI assistant for triage guidance only.
            It does not provide medical diagnoses. Always consult a qualified healthcare professional.
            In emergencies, call <strong>911</strong> or <strong>112</strong> immediately.
        </div>
        """)

        # ── Event Bindings ─────────────────────────────────────────────
        outputs = [
            chatbot, conv_context,
            status_display, symptoms_display,
            severity_display, department_display,
            appointment_display, msg,
        ]

        msg.submit(
            respond,
            inputs=[msg, chatbot, conv_context],
            outputs=outputs,
        )

        send_btn.click(
            respond,
            inputs=[msg, chatbot, conv_context],
            outputs=outputs,
        )

        clear_btn.click(
            reset_conversation,
            inputs=None,
            outputs=[
                chatbot, conv_context,
                status_display, symptoms_display,
                severity_display, department_display,
                appointment_display,
            ],
        )

    return app


# ── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=8000,
        share=False,
        show_error=True,
    )
