import asyncio

from langchain_core.messages import HumanMessage

from agent.graph import build_graph
from agent.mcp_client import mcp_client

async def main():
    # MCP must be connected before the booking subgraph runs — the subgraph's
    # nodes call mcp_client.call_tool() directly. In production this connection
    # is owned by the FastAPI lifespan; for the scratch we manage it manually.
    await mcp_client.connect()
    try:
        # No checkpointer for the smoke test — we manually forward `state` between
        # turns, which mirrors what production will do once Postgres is wired up.
        graph = build_graph(checkpointer=None)

        # --- Turn 1: a booking request ---
        # Note: no manual `response: None` — normalize_input now handles that.
        state = await graph.ainvoke({
            "patient_id": "test",
            "openmrs_patient_id": "ABC200000",
            "channel": "web",
            "messages": [HumanMessage(content="I need a general medicine doctor wednesday morning")],
        })
        print("\n--- TURN 1 ---")
        print("current_flow:     ", state.get("current_flow"))
        print("flow_state.step:  ", state.get("flow_state", {}).get("step"))
        print("formatted_response:", state.get("formatted_response"))

        # --- Turn 2: pick option 1 ---
        # We append the new message and re-invoke. The mid-flow router in the
        # parent graph sees current_flow="booking" + flow_state.step="awaiting_selection"
        # and skips classify_intent, going straight back to the booking subgraph.
        state["messages"].append(HumanMessage(content="1"))
        state = await graph.ainvoke(state)
        
        print("\n--- TURN 2 ---")
        print("current_flow:     ", state.get("current_flow"))
        print("flow_state.step:  ", state.get("flow_state", {}).get("step"))  # should be None after confirm
        print("formatted_response:", state.get("formatted_response"))
        
    finally:
        await mcp_client.close()

asyncio.run(main())