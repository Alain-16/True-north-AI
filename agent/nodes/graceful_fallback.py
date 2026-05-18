from langchain_core.messages import HumanMessage
from agent.state import AgentState
from agent.llm_client import llm

FALLBACK_SYSTEM_PROMPT = """
 You are MediAgent, a hospital patient assistant.

  You can help patients with exactly these five things:
  1. Book, reschedule, or cancel a doctor appointment
  2. Understand a lab result or prescription
  3. Check their current queue position and wait time
  4. Get symptom guidance and find the right department
  5. Manage appointment reminders and follow-up schedules

  The patient sent a message you could not classify into one of those five areas.
  Acknowledge what they said briefly, then explain what you can help with in plain,
  friendly language. Do not use medical jargon. Keep your response under 3 sentences.
"""
async def graceful_fallback(state:AgentState) -> dict:

    user_messages = [m for m in state.messages if isinstance(m,HumanMessage)]

    if user_messages:
        prompt = f'Patient said: "{user_messages[-1].content}"\n\nRespond helpfully.'
    else:
        prompt = "The patient sent an empty or unreadable message. Ask them what you can help with."

    reply = await llm.simple(
        prompt=prompt,
        system=FALLBACK_SYSTEM_PROMPT,
        max_tokens=256,
    )

    return{
        "response":{"type":"text","content":reply},
        "current_flow":None,
    }