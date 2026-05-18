import pytest
from pydantic import ValidationError
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph.message import add_messages

from agent.state import AgentState


class TestAgentStateDefaults:
      def test_default_values(self):
          state = AgentState(
              patient_id="p1",
              openmrs_patient_id="OP-1",
              channel="web",
          )
          assert state.messages == []
          assert state.current_flow is None
          assert state.flow_state == {}
          assert state.pending_intent is None
          assert state.error is None
          assert state.retry_count == 0
          assert state.response is None
          assert state.formatted_response is None

      def test_explicit_values_are_stored(self):
          state = AgentState(
              patient_id="abc-123",
              openmrs_patient_id="OP-456",
              channel="whatsapp",
              current_flow="booking",
              retry_count=1,
              error="fhir_timeout",
          )
          assert state.patient_id == "abc-123"
          assert state.current_flow == "booking"
          assert state.retry_count == 1
          assert state.error == "fhir_timeout"


class TestAddMessagesReducer:
      def test_appends_to_existing(self):
          existing = [HumanMessage(content="first message")]
          new = [AIMessage(content="agent reply")]

          result = add_messages(existing, new)

          assert len(result) == 2
          assert result[0].content == "first message"
          assert result[1].content == "agent reply"

      def test_empty_existing_list(self):
          result = add_messages([], [HumanMessage(content="hello")])

          assert len(result) == 1
          assert result[0].content == "hello"

      def test_multiple_new_messages(self):
          existing = [HumanMessage(content="turn 1")]
          new = [
              AIMessage(content="response 1"),
              HumanMessage(content="turn 2"),
          ]

          result = add_messages(existing, new)

          assert len(result) == 3

      def test_does_not_replace_existing(self):
          # Core guarantee: reducer must NEVER wipe history.
          # If this assertion fails, the Annotated[list, add_messages] wiring
          # on AgentState.messages has been broken.
          existing = [HumanMessage(content="do not lose me")]
          new = [HumanMessage(content="new message")]

          result = add_messages(existing, new)

          contents = [m.content for m in result]
          assert "do not lose me" in contents


class TestChannelValidation:
      def test_accepts_whatsapp(self):
          state = AgentState(
              patient_id="p1",
              openmrs_patient_id="OP-1",
              channel="whatsapp",
          )
          assert state.channel == "whatsapp"

      def test_accepts_web(self):
          state = AgentState(
              patient_id="p1",
              openmrs_patient_id="OP-1",
              channel="web",
          )
          assert state.channel == "web"

      def test_rejects_invalid_channel(self):
            with pytest.raises(ValidationError) as exc_info:
                AgentState(
                patient_id="p1",
                openmrs_patient_id="OP-1",
                channel="sms",
             )
            assert "channel" in str(exc_info.value)

      def test_rejects_empty_string(self):
          with pytest.raises(ValidationError):
              AgentState(
                  patient_id="p1",
                  openmrs_patient_id="OP-1",
                  channel="",
              )