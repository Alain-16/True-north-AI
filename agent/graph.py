from langgraph.graph import StateGraph,START,END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from agent.state import AgentState
from agent.nodes.normalize_input import normalize_input
from agent.nodes.classify_intent import classify_intent
from agent.nodes.format_channel import format_for_web,format_for_whatsapp
from agent.nodes.graceful_fallback import graceful_fallback

async def _stub(flow_name: str,state:AgentState)-> dict:
    return{
        "response":{
            "type": "text",
            "content":f"The {flow_name} feature is coming soon.",
        }
    }

async def booking_stub(state:AgentState) -> dict:
    return await _stub("booking",state)
async def triage_stub(state: AgentState) -> dict:
    return await _stub("triage", state)

async def reports_stub(state: AgentState) -> dict:
    return await _stub("reports", state)

async def queue_stub(state: AgentState) -> dict:
    return await _stub("queue", state)

async def reminders_stub(state: AgentState) -> dict:
    return await _stub("reminders", state)

_MAIN_FLOWS = {"booking","triage","reports","queue","reminders"}

def route_intent(state: AgentState)-> str:
    flow = state.current_flow
    
    if flow in _MAIN_FLOWS:
        return flow
    
    if flow == "resume_flow":
        pending = (state.pending_intent or {}).get("flow")
        if pending in _MAIN_FLOWS:
            return pending
        
        return "graceful_fallback"
    return "graceful_fallback"

def route_channel(state:AgentState)->str:
    if state.channel == "whatsapp":
        return "format_for_whatsapp"
    return "format_for_web"


_RESPONSE_NODES = [*_MAIN_FLOWS,"graceful_fallback"]

def build_graph(checkpointer:AsyncPostgresSaver | None = None)-> CompiledStateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("normalize_input", normalize_input)
    graph.add_node("classify_intent",     classify_intent)
    graph.add_node("booking",             booking_stub)
    graph.add_node("triage",              triage_stub)
    graph.add_node("reports",             reports_stub)
    graph.add_node("queue",               queue_stub)
    graph.add_node("reminders",           reminders_stub)
    graph.add_node("graceful_fallback",   graceful_fallback)
    graph.add_node("format_for_whatsapp", format_for_whatsapp)
    graph.add_node("format_for_web",      format_for_web)

    graph.add_edge(START,"normalize_input")
    graph.add_edge("normalize_input","classify_intent")

    graph.add_conditional_edges(
        "classify_intent",
        route_intent,
        {flow:flow for flow in _MAIN_FLOWS} | {"graceful_fallback":"graceful_fallback"},


    )

    channel_map = {
        "format_for_whatsapp":"format_for_whatsapp",
        "format_for_web":"format_for_web",
    }

    for node in _RESPONSE_NODES:
        graph.add_conditional_edges(node,route_channel,channel_map)

    graph.add_edge("format_for_whatsapp",END)
    graph.add_edge("format_for_web",END)

    return graph.compile(checkpointer=checkpointer)