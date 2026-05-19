import json
import uuid
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from agent.state import AgentState
  

  # ---------------------------------------------------------------------------
  # Helpers
  # ---------------------------------------------------------------------------

def make_initial_state(message: str, channel: str = "web", pending_intent=None) -> dict:
      state = {
          "messages":           [HumanMessage(content=message)],
          "patient_id":         "test-patient-1",
          "openmrs_patient_id": "OP-TEST-1",
          "channel":            channel,
      }
      if pending_intent:
          state["pending_intent"] = pending_intent
      return state


def unique_thread() -> dict:
      """Each test gets its own thread so MemorySaver checkpoints don't collide."""
      return {"configurable": {"thread_id": str(uuid.uuid4())}}
  

def mock_classify(mocker, intent: str, confidence: float = 0.95):
      return mocker.patch(
          "agent.nodes.classify_intent.llm.simple",
          new=AsyncMock(return_value=f'{{"intent": "{intent}", "confidence": {confidence}}}'),
      )


  # ---------------------------------------------------------------------------
  # Routing tests
  # ---------------------------------------------------------------------------

class TestGraphRouting:

      async def test_happy_path_returns_formatted_response(self, graph, mocker):
          mock_classify(mocker, "booking")
          final = await graph.ainvoke(make_initial_state("Book me a doctor"), unique_thread())
          assert final["formatted_response"] is not None
          assert len(final["formatted_response"]) > 0
  
      async def test_web_channel_returns_valid_json(self, graph, mocker):
          mock_classify(mocker, "booking")
          final = await graph.ainvoke(make_initial_state("Book me a doctor"), unique_thread())
          # format_for_web must always produce parseable JSON
          payload = json.loads(final["formatted_response"])
          assert "type" in payload
          assert "content" in payload

      @pytest.mark.parametrize("flow", ["booking", "triage", "reports", "queue", "reminders"])
      async def test_all_intents_route_to_correct_subgraph(self, graph, mocker, flow):
          mock_classify(mocker, flow)
          final = await graph.ainvoke(make_initial_state("test message"), unique_thread())
          assert final["current_flow"] == flow

      async def test_unknown_intent_produces_fallback_response(self, graph, mocker):
          mock_classify(mocker, "unknown")
          mocker.patch(
              "agent.nodes.graceful_fallback.llm.simple",
              new=AsyncMock(return_value="I can help you with booking, triage, and more."),
          )
          final = await graph.ainvoke(make_initial_state("huh?"), unique_thread())
          payload = json.loads(final["formatted_response"])
          assert "I can help you" in payload["content"]

      async def test_low_confidence_routes_to_fallback(self, graph, mocker):
          mock_classify(mocker, "booking", confidence=0.40)
          mocker.patch(
              "agent.nodes.graceful_fallback.llm.simple",
              new=AsyncMock(return_value="Here's what I can do."),
          )
          final = await graph.ainvoke(make_initial_state("maybe?"), unique_thread())
          # Low confidence → classify_intent returns unknown → graceful_fallback runs
          payload = json.loads(final["formatted_response"])
          assert payload["type"] == "text"


  # ---------------------------------------------------------------------------
  # Multi-turn tests
  # ---------------------------------------------------------------------------

class TestMultiTurn:

      async def test_messages_accumulate_across_turns(self, graph, mocker):
          mocker.patch(
              "agent.nodes.classify_intent.llm.simple",
              new=AsyncMock(side_effect=[
                  '{"intent": "booking", "confidence": 0.95}',  # turn 1
                  '{"intent": "queue",   "confidence": 0.90}',  # turn 2
              ]),
          ) 
          config = unique_thread()

          await graph.ainvoke(make_initial_state("Book a doctor"), config)
          final = await graph.ainvoke(make_initial_state("How long is the wait?"), config)

          # Both turns' messages must be present — MemorySaver restored turn 1
          assert len(final["messages"]) >= 2

      async def test_second_turn_reflects_new_intent(self, graph, mocker):
          mocker.patch(
              "agent.nodes.classify_intent.llm.simple",
              new=AsyncMock(side_effect=[
                  '{"intent": "booking", "confidence": 0.95}',
                  '{"intent": "triage",  "confidence": 0.92}',
              ]),
          )
          config = unique_thread()

          await graph.ainvoke(make_initial_state("Book a doctor"), config)
          final = await graph.ainvoke(make_initial_state("I have chest pain"), config)

          assert final["current_flow"] == "triage"


  # ---------------------------------------------------------------------------
  # Interrupt / resume tests
  # ---------------------------------------------------------------------------

class TestInterruptResume:

    async def test_resume_flow_restores_pending_subgraph(self, graph, mocker):
        mock_classify(mocker, "resume_flow")
        initial = make_initial_state(
            "yes please continue",
            pending_intent={"flow": "triage", "flow_state": {"symptoms": "headache"}},
        )
        final = await graph.ainvoke(initial, unique_thread())
        # current_flow stays "resume_flow" — classify_intent set it and the stub
        # doesn't overwrite it. Verify routing succeeded by checking the triage
        # stub's content reached the formatted response.
        payload = json.loads(final["formatted_response"])
        assert "triage" in payload["content"]
  
    async def test_resume_flow_without_pending_intent_falls_back(self, graph, mocker):
          mock_classify(mocker, "resume_flow")
          mocker.patch(
              "agent.nodes.graceful_fallback.llm.simple",
              new=AsyncMock(return_value="Nothing to resume."),
          )
          # pending_intent is None — nothing to restore
          final = await graph.ainvoke(make_initial_state("yes continue"), unique_thread())
          payload = json.loads(final["formatted_response"])
          assert payload["type"] == "text"
