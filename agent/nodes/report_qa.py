import uuid
import logging

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select

from core.database import AsyncSessionLocal
from models.db import ReportDeliveryLog
from agent.state import AgentState
from agent.llm_client import llm

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "This is an explanation of your existing record, not a new diagnosis. "
    "Please confirm anything that affects your care with your doctor."
)

SYSTEM = """You are TrueNorth-AI, a careful patient-facing health assistant at St. Mary's Hospital.

The patient has already received this explanation of their {resource_type}:
<explanation>
{explanation}
</explanation>

The patient now has a follow-up question about it. Answer using ONLY the explanation above plus general, non-diagnostic health information.

Rules:
- Do NOT invent specific values, results, dosages, or diagnoses that are not in the explanation.
- If the question cannot be answered from the explanation, say so plainly and suggest they ask their care team.
- Keep it short, plain-language, calm, and accurate. No markdown headers.
- Never tell the patient to start, stop, or change a medication or treatment — direct them to their doctor for those decisions.
"""

# Anthropic-style message conversion (mirrors triage._messages_for_llm).
def _messages_for_llm(state: AgentState) -> list[dict]:
    out: list[dict] = []
    for m in state.messages:
        if isinstance(m, HumanMessage):
            out.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            out.append({"role": "assistant", "content": m.content})
    return out


async def report_qa(state: AgentState) -> dict:
    """Answer a follow-up question grounded in a specific delivered report's
    stored explanation. Entered only when state.report_id is set."""

    not_found = {
        "response": {
            "type": "text",
            "content": (
                "I couldn't find that report's explanation. Please open it from your "
                "Reports section and try asking again."
            ),
        }
    }

    try:
        report_uuid = uuid.UUID(state.report_id)
        patient_uuid = uuid.UUID(state.patient_id)
    except (ValueError, TypeError):
        return not_found

    async with AsyncSessionLocal() as session:
        row = (await session.execute(
            select(ReportDeliveryLog).where(
                ReportDeliveryLog.id == report_uuid,
                # Scope to the authenticated patient — never answer about another
                # patient's report even if an id is guessed.
                ReportDeliveryLog.patient_id == patient_uuid,
            )
        )).scalar_one_or_none()

    if row is None or not row.ai_explanation_summary:
        return not_found

    system = SYSTEM.format(
        resource_type=row.resource_type,
        explanation=row.ai_explanation_summary,
    )

    try:
        answer = await llm.complex(messages=_messages_for_llm(state), system=system)
    except Exception:
        logger.exception("report_qa LLM call failed for report_id=%s", state.report_id)
        return {
            "response": {
                "type": "text",
                "content": "Sorry — I couldn't answer that just now. Please try again in a moment.",
            }
        }

    content = answer.strip()
    if DISCLAIMER not in content:
        content = f"{content}\n\n{DISCLAIMER}"

    return {
        "messages": [AIMessage(content=answer.strip())],
        "response": {"type": "text", "content": content},
    }
