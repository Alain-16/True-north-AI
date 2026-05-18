from langchain_core.messages import HumanMessage
from agent.state import AgentState

async def normalize_input(state:AgentState) -> dict:

    last = state.messages[-1] if state.messages else None

    updates : dict = {"retry_count":0}

    if last and not isinstance(last,HumanMessage):
        content = last.get("content","") if isinstance(last,dict) else str(last)
        updates["messages"] = [HumanMessage(content=content)]

    return updates