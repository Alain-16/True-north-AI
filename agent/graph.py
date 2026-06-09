from langgraph.graph import StateGraph,START,END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from agent.state import AgentState
from agent.nodes.normalize_input import normalize_input
from agent.nodes.classify_intent import classify_intent
from agent.nodes.format_channel import format_for_web,format_for_whatsapp
from agent.nodes.graceful_fallback import graceful_fallback
from agent.subgraphs.booking import build_booking_subgraph
from agent.subgraphs.triage import build_triage_subgraph
from agent.nodes.report_qa import report_qa

async def _stub(flow_name: str,state:AgentState)-> dict:
    return{
        "response":{
            "type": "text",
            "content":f"The {flow_name} feature is coming soon.",
        }
    }

async def reports_stub(state: AgentState) -> dict:
    # Report interpretation is event-driven by design (F4): explanations are
    # generated when a lab/prescription is posted and delivered to the patient's
    # Reports section. We don't answer report questions inline in chat — redirect
    # the patient there instead of the generic "coming soon" stub.
    return {
        "response": {
            "type": "text",
            "content": (
                "Your lab results and prescription explanations are added to your "
                "Reports section automatically as soon as your care team posts them — "
                "open any of them there to see a plain-language explanation. I can't "
                "pull them into this chat directly yet."
            ),
        }
    }

async def queue_stub(state: AgentState) -> dict:
    return await _stub("queue", state)

async def reminders_stub(state: AgentState) -> dict:
    return await _stub("reminders", state)

_MAIN_FLOWS = {"booking","triage","reports","queue","reminders"}

def route_after_normalization(state:AgentState)-> str:
    # A report follow-up is an explicit, contextual override: the patient clicked
    # "ask about this report", so skip intent classification and any active flow.
    if state.report_id:
        return "report_qa"
    if state.current_flow in _MAIN_FLOWS and state.flow_state.get("step"):
        return state.current_flow
    return "classify_intent"

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

def route_after_triage(state:AgentState)-> str:
    if state.response is None and state.flow_state.get("specialty"):
        return "booking"
    if state.channel == "whatsapp":
        return "format_for_whatsapp"
    return "format_for_web"

_RESPONSE_NODES = [flow for flow in _MAIN_FLOWS if flow != "triage"] + ["graceful_fallback", "report_qa"]

def build_graph(checkpointer:AsyncPostgresSaver | None = None)-> CompiledStateGraph:
    graph = StateGraph(AgentState)

    booking_subgraph = build_booking_subgraph()
    triage_subgraph = build_triage_subgraph()

    graph.add_node("normalize_input", normalize_input)
    graph.add_node("classify_intent",     classify_intent)
    graph.add_node("booking",             booking_subgraph)
    graph.add_node("triage",              triage_subgraph)
    graph.add_node("reports",             reports_stub)
    graph.add_node("report_qa",           report_qa)
    graph.add_node("queue",               queue_stub)
    graph.add_node("reminders",           reminders_stub)
    graph.add_node("graceful_fallback",   graceful_fallback)
    graph.add_node("format_for_whatsapp", format_for_whatsapp)
    graph.add_node("format_for_web",      format_for_web)

    graph.add_edge(START,"normalize_input")
    graph.add_conditional_edges(
        "normalize_input",
        route_after_normalization,
        {"classify_intent":"classify_intent", "report_qa":"report_qa"} | {flow: flow for flow in _MAIN_FLOWS},
    )

    graph.add_conditional_edges(
        "classify_intent",
        route_intent,
        {flow:flow for flow in _MAIN_FLOWS} | {"graceful_fallback":"graceful_fallback"},


    )

    graph.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "booking": "booking",
            "format_for_whatsapp": "format_for_whatsapp",
            "format_for_web": "format_for_web",
        },
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