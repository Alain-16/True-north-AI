from typing import Annotated, Literal, Optional
from langgraph.graph.message import add_messages
from pydantic import BaseModel


class AgentState(BaseModel):
    patient_id: str
    openmrs_patient_id: str

    channel: Literal["whatsapp","web"]

    messages: Annotated[list, add_messages]=[]

    current_flow: Optional[str] = None

    flow_state: dict={}

    pending_intent: Optional[dict] = None

    error: Optional[str] = None

    retry_count: int = 0

    response: Optional[dict] = None
    formatted_response: Optional[str] = None