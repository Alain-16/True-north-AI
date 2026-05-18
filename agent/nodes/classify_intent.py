import json
from langchain_core.messages import HumanMessage
from agent.state import AgentState
from agent.llm_client import llm

INTENT_SYSTEM_PROMPT = """

You are an intent classifier for MediAgent, a hospital patient assistant.

  Classify the patient's message into exactly one of these intents:

  booking    — Patient wants to find a doctor, check availability, or book/cancel/reschedule an appointment.
               Examples: "I need to see a doctor", "Book me with Dr. Mugisha", "Cancel my Thursday appointment"

  triage     — Patient describes symptoms and wants guidance on which department to visit or how urgent it is.
               Examples: "I have chest pain", "My child has had a fever for 3 days", "I've been having headaches"

  reports    — Patient wants to understand a lab result, prescription, or uploaded medical document.
               Examples: "What does my blood test mean?", "Explain my prescription", "I uploaded my scan"

  queue      — Patient wants their current queue position or wait time estimate.
               Examples: "How long is the wait?", "Where am I in the queue?", "How many people ahead of me?"

  reminders  — Patient wants to manage appointment reminders or their follow-up schedule.
               Examples: "Remind me about my appointment", "Turn off reminders", "When is my next check-up?"

  resume_flow — Patient is responding to continue a previously interrupted conversation.
               Examples: "Yes, continue", "Let's go back to booking", "Yes please"

  unknown    — Message does not match any intent above.

  Return valid JSON only. No explanation, no markdown, no code fences.
  {"intent": "<intent>", "confidence": <float 0.0–1.0>}
"""

VALID_INTENTS = {"booking","triage","reports","queue","reminders","resume_flow","unknown"}

async def classify_intent(state: AgentState) -> dict:
    user_messages =[m for m in state.messages if isinstance(m, HumanMessage)]
    if not user_messages:
        return{"current_flow": "unknown"}
    
    latest = user_messages[-1].content
    context = ""
    if state.pending_intent:
        context = (
            f"The patient previously had an active '{state.pending_intent['flow']}'"
            f"conversation that was interrupted.\n\n"
        )

    raw = await llm.simple(
        prompt=f"{context}Patient message: {latest}",
        system = INTENT_SYSTEM_PROMPT,
    )

    try:
        result = json.loads(raw)
        intent = result.get("intent","unknown")
        confidence = float(result.get("confidence",0.0))
        if confidence < 0.6 or intent not in VALID_INTENTS:
            intent = "unknown"
    
    except(json.JSONDecodeError,ValueError,KeyError):
        intent = "unknown"

    return {"current_flow":intent,"error":None}