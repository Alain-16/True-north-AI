from unittest.mock import AsyncMock
import pytest
from langchain_core.messages import HumanMessage
from agent.state import AgentState
from agent.nodes.normalize_input import normalize_input
from agent.nodes.classify_intent import classify_intent
from agent.nodes.graceful_fallback import graceful_fallback


  # ---------------------------------------------------------------------------
  # Helpers
  # ---------------------------------------------------------------------------

def make_state(messages=None, pending_intent=None, retry_count=0, current_flow=None):
      return AgentState.model_construct(
          messages=messages or [],
          pending_intent=pending_intent,
          retry_count=retry_count,
          current_flow=current_flow,
          patient_id="p1",
          openmrs_patient_id="OP-1",
          channel="web",
      )


  # ---------------------------------------------------------------------------
  # normalize_input
  # ---------------------------------------------------------------------------

class TestNormalizeInput:

      async def test_resets_retry_count(self):
          state = make_state(retry_count=2)
          result = await normalize_input(state)
          assert result["retry_count"] == 0

      async def test_converts_dict_message_to_human_message(self):
          state = make_state(messages=[{"role": "user", "content": "hello"}])
          result = await normalize_input(state)
          wrapped = result["messages"][0]
          assert isinstance(wrapped, HumanMessage)
          assert wrapped.content == "hello"

      async def test_does_not_double_wrap_human_message(self):
          state = make_state(messages=[HumanMessage(content="hello")])
          result = await normalize_input(state)
          # Already a HumanMessage — no messages update should be returned
          assert "messages" not in result

      async def test_empty_messages_does_not_crash(self):
          state = make_state(messages=[])
          result = await normalize_input(state)
          assert result["retry_count"] == 0


  # ---------------------------------------------------------------------------
  # classify_intent
  # ---------------------------------------------------------------------------

class TestClassifyIntent:

      async def test_valid_intent_sets_current_flow(self, mocker):
          mocker.patch(
              "agent.nodes.classify_intent.llm.simple",
              new=AsyncMock(return_value='{"intent": "booking", "confidence": 0.95}'),
          )
          state = make_state(messages=[HumanMessage(content="I need to book a doctor")])
          result = await classify_intent(state)
          assert result["current_flow"] == "booking"

      async def test_low_confidence_returns_unknown(self, mocker):
          mocker.patch(
              "agent.nodes.classify_intent.llm.simple",
              new=AsyncMock(return_value='{"intent": "booking", "confidence": 0.45}'),
          )
          state = make_state(messages=[HumanMessage(content="maybe a doctor")])
          result = await classify_intent(state)
          assert result["current_flow"] == "unknown"

      async def test_malformed_json_returns_unknown(self, mocker):
          mocker.patch(
              "agent.nodes.classify_intent.llm.simple",
              new=AsyncMock(return_value="I cannot classify this message"),
          )
          state = make_state(messages=[HumanMessage(content="something")])
          result = await classify_intent(state)
          assert result["current_flow"] == "unknown"

      async def test_unrecognised_intent_name_returns_unknown(self, mocker):
          # High confidence on a made-up intent must still be rejected
          mocker.patch(
              "agent.nodes.classify_intent.llm.simple",
              new=AsyncMock(return_value='{"intent": "dancing", "confidence": 0.99}'),
          )
          state = make_state(messages=[HumanMessage(content="something")])
          result = await classify_intent(state)
          assert result["current_flow"] == "unknown"

      async def test_empty_messages_skips_llm_call(self, mocker):
          mock_llm = mocker.patch(
              "agent.nodes.classify_intent.llm.simple",
              new=AsyncMock(),
          )
          state = make_state(messages=[])
          result = await classify_intent(state)
          assert result["current_flow"] == "unknown"
          mock_llm.assert_not_called()

      async def test_pending_intent_adds_flow_context_to_prompt(self, mocker):
          mock_llm = mocker.patch(
              "agent.nodes.classify_intent.llm.simple",
              new=AsyncMock(return_value='{"intent": "resume_flow", "confidence": 0.90}'),
          )
          state = make_state(
              messages=[HumanMessage(content="yes please continue")],
              pending_intent={"flow": "booking", "flow_state": {}},
          )
          await classify_intent(state)

          # The prompt must reference the interrupted flow so the classifier
          # can correctly identify "yes continue" as resume_flow
          call_kwargs = mock_llm.call_args.kwargs
          prompt = call_kwargs.get("prompt") or mock_llm.call_args.args[0]
          assert "booking" in prompt

      async def test_error_field_cleared_on_success(self, mocker):
          mocker.patch(
              "agent.nodes.classify_intent.llm.simple",
              new=AsyncMock(return_value='{"intent": "queue", "confidence": 0.88}'),
          )
          state = make_state(messages=[HumanMessage(content="how long is the wait?")])
          result = await classify_intent(state)
          assert result["error"] is None


  # ---------------------------------------------------------------------------
  # graceful_fallback
  # ---------------------------------------------------------------------------

class TestGracefulFallback:

      async def test_returns_text_response(self, mocker):
          mocker.patch(
              "agent.nodes.graceful_fallback.llm.simple",
              new=AsyncMock(return_value="Here's how I can help you today."),
          )
          state = make_state(messages=[HumanMessage(content="huh?")])
          result = await graceful_fallback(state)
          assert result["response"]["type"] == "text"
          assert result["response"]["content"] == "Here's how I can help you today."

      async def test_clears_current_flow(self, mocker):
          mocker.patch(
              "agent.nodes.graceful_fallback.llm.simple",
              new=AsyncMock(return_value="Let me help."),
          )
          state = make_state(current_flow="unknown")
          result = await graceful_fallback(state)
          assert result["current_flow"] is None

      async def test_uses_simple_not_complex(self, mocker):
          mock_simple = mocker.patch(
              "agent.nodes.graceful_fallback.llm.simple",
              new=AsyncMock(return_value="Here to help."),
          )
          mock_complex = mocker.patch(
              "agent.nodes.graceful_fallback.llm.complex",
              new=AsyncMock(),
          )
          state = make_state(messages=[HumanMessage(content="?")])
          await graceful_fallback(state)
          mock_simple.assert_called_once()
          mock_complex.assert_not_called()

      async def test_empty_messages_does_not_crash(self, mocker):
          mocker.patch(
              "agent.nodes.graceful_fallback.llm.simple",
              new=AsyncMock(return_value="How can I help?"),
          )
          state = make_state(messages=[])
          result = await graceful_fallback(state)
          assert result["response"]["type"] == "text"
