from langgraph.graph import StateGraph,START,END
from langgraph.graph.state import CompiledStateGraph
from agent.state import AgentState
import json
from langchain_core.messages import HumanMessage
from agent.llm_client import llm

EXTRACT_SYSTEM_PROMPT="""

  You extract appointment-booking details from a patient's message.

  Return valid JSON only — no explanation, no markdown, no code fences:
  {"specialty": <string or null>, "date_preference": <string or null>, "time_preference": <string or null>}

  specialty       — the type of doctor or department the patient wants
                    (e.g. "dermatology", "ENT", "general medicine"). null if not stated.
  date_preference — any date hint in the patient's own words
                    (e.g. "this week", "next Monday", "tomorrow", "as soon as possible"). null if not stated.
  time_preference — any time-of-day hint (e.g. "morning", "afternoon", "9 AM"). null if not stated.


"""

async def extract_params(state: AgentState) -> dict:
      user_message = [m for m in state.messages if isinstance(m,HumanMessage)]
      latest = user_message[-1].content if user_message else ""
      
      raw = await llm.simple(
            prompt=f"Patient message:{latest}",
            system=EXTRACT_SYSTEM_PROMPT
      )
      try:
            parsed= json.loads(raw)
      except (json.JSONDecodeError,ValueError):
            parsed={}
            
      return {
            "flow_state":{
                  **state.flow_state,
                  "speciality":parsed.get("speciality"),
                  "date_preference":parsed.get("date_preference"),
                  "time_preference":parsed.get("time_preference"),

            }
      }


async def resolve_service(state: AgentState) -> dict:
      return {}


async def generate_slots(state: AgentState) -> dict:
      return {}


async def present_slots(state: AgentState) -> dict:
      return {}


async def handle_selection(state: AgentState) -> dict:
      return {}


async def confirm_create(state: AgentState) -> dict:
      return {}

def route_entry(state:AgentState)-> str:
      step = state.flow_state.get("step")
      if step == "awaiting_selection":
            return "handle_selection"
      return "extract_params"

def build_booking_subgraph() -> CompiledStateGraph:
      graph = StateGraph(AgentState)

      graph.add_node("extract_params",extract_params)
      graph.add_node("resolve_service",resolve_service)
      graph.add_node("generate_slots",generate_slots)
      graph.add_node("present_slots",present_slots)
      graph.add_node("handle_selection",handle_selection)
      graph.add_node("confirm_create",confirm_create)

      graph.add_conditional_edges(
            START,
            route_entry,
            {
                  "extract_params":"extract_params",
                  "handle_selection":"handle_selection",
            },

      )

      graph.add_edge("extract_params","resolve_service")
      graph.add_edge("resolve_service","generate_slots")
      graph.add_edge("generate_slots","present_slots")
      graph.add_edge("present_slots",END)

      return graph.compile()