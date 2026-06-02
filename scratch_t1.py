import asyncio

from langchain_core.messages import HumanMessage

from agent.mcp_client import mcp_client
from agent.graph import build_graph


def _print_turn(state: dict, label: str) -> None:
      print(f"\n--- {label} ---")
      print("current_flow:    ", state.get("current_flow"))
      print("flow_state.step: ", state.get("flow_state", {}).get("step"))
      print("flow_state keys: ", list(state.get("flow_state", {}).keys()))
      print("formatted_response:", state.get("formatted_response"))


async def main():
      await mcp_client.connect()
      try:
          graph = build_graph(checkpointer=None)

          # Turn 1: symptom description (rich enough to classify in one shot) →
          # triage classifies → asks "want me to book?"
          state = await graph.ainvoke({
              "patient_id": "test",
              "openmrs_patient_id": "ABC200000",
              "channel": "web",
              "messages": [HumanMessage(content=(
                  "I've had a sore throat for 3 days, getting better actually. "
                  "It's mild — maybe 3 out of 10. Slight fever, no trouble swallowing "
                  "or breathing, no rash, still able to eat and drink normally."
              ))],
          })
          _print_turn(state, "TURN 1 (triage classify)")

          # Turn 2: accept → triage hands off to booking → booking presents slots.
          # The critical handoff turn: patient sees booking's slot list, NOT a
          # triage acknowledgment.
          state["messages"].append(HumanMessage(content="yes"))
          state = await graph.ainvoke(state)
          _print_turn(state, "TURN 2 (accept → booking handoff)")

          # Turn 3: pick slot 1 → booking confirms appointment, mirrors to DB,
          # seeds reminder rows.
          state["messages"].append(HumanMessage(content="1"))
          state = await graph.ainvoke(state)
          _print_turn(state, "TURN 3 (slot pick → confirm)")

      finally:
          await mcp_client.close()


asyncio.run(main())