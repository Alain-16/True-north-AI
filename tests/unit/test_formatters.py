import json
import pytest
from agent.state import AgentState
from agent.nodes.format_channel import format_for_whatsapp, format_for_web


def make_state(response=None):
      return AgentState.model_construct(response=response)


  # ---------------------------------------------------------------------------
  # format_for_whatsapp
  # ---------------------------------------------------------------------------

class TestFormatForWhatsapp:

      async def test_text_type_returns_content(self):
          state = make_state({"type": "text", "content": "Hello, how can I help?"})
          result = await format_for_whatsapp(state)
          assert result["formatted_response"] == "Hello, how can I help?"

      async def test_appointment_card_contains_metadata(self):
          state = make_state({
              "type": "appointment_card",
              "content": "Your appointment is confirmed.",
              "metadata": {
                  "doctor_name": "Dr. Mugisha",
                  "specialty": "Dermatology",
                  "scheduled_at": "Wed 18 Jun at 09:00",
              },
          })
          result = await format_for_whatsapp(state)
          text = result["formatted_response"]
          assert "Dr. Mugisha" in text
          assert "Dermatology" in text
          assert "Wed 18 Jun at 09:00" in text

      async def test_queue_status_contains_position_and_wait(self):
          state = make_state({
              "type": "queue_status",
              "content": "",
              "metadata": {"position": 3, "wait_minutes": 20},
          })
          result = await format_for_whatsapp(state)
          text = result["formatted_response"]
          assert "3" in text
          assert "20" in text

      async def test_triage_result_shows_urgency_uppercase(self):
          state = make_state({
              "type": "triage_result",
              "content": "Please visit the cardiology department.",
              "metadata": {"urgency": "urgent"},
          })
          result = await format_for_whatsapp(state)
          assert "URGENT" in result["formatted_response"]

      async def test_strips_bold_markdown(self):
          state = make_state({"type": "text", "content": "**Important** result"})
          result = await format_for_whatsapp(state)
          assert "**" not in result["formatted_response"]
          assert "Important" in result["formatted_response"]

      async def test_strips_header_markdown(self):
          state = make_state({"type": "text", "content": "## Your Results\nAll normal."})
          result = await format_for_whatsapp(state)
          assert "##" not in result["formatted_response"]
          assert "Your Results" in result["formatted_response"]

      async def test_strips_inline_code_markdown(self):
          state = make_state({"type": "text", "content": "Take `metformin` daily."})
          result = await format_for_whatsapp(state)
          assert "`" not in result["formatted_response"]
          assert "metformin" in result["formatted_response"]

      async def test_truncates_long_content(self):
          state = make_state({"type": "text", "content": "a" * 2000})
          result = await format_for_whatsapp(state)
          assert len(result["formatted_response"]) == 1600
          assert result["formatted_response"].endswith("...")

      async def test_content_under_limit_is_not_truncated(self):
          content = "a" * 100
          state = make_state({"type": "text", "content": content})
          result = await format_for_whatsapp(state)
          assert len(result["formatted_response"]) == 100

      async def test_missing_metadata_falls_back_to_tbd(self):
          state = make_state({
              "type": "appointment_card",
              "content": "Confirmed.",
              # metadata key is absent entirely
          })
          result = await format_for_whatsapp(state)
          assert "TBD" in result["formatted_response"]

      async def test_none_response_does_not_crash(self):
          state = make_state(response=None)
          result = await format_for_whatsapp(state)
          assert isinstance(result["formatted_response"], str)
          assert len(result["formatted_response"]) > 0


  # ---------------------------------------------------------------------------
  # format_for_web
  # ---------------------------------------------------------------------------

class TestFormatForWeb:

      async def test_output_is_valid_json(self):
          state = make_state({"type": "text", "content": "Hello"})
          result = await format_for_web(state)
          # Must not raise
          payload = json.loads(result["formatted_response"])
          assert isinstance(payload, dict)

      async def test_all_four_keys_always_present(self):
          state = make_state({"type": "text", "content": "Hello"})
          result = await format_for_web(state)
          payload = json.loads(result["formatted_response"])
          assert "type" in payload
          assert "content" in payload
          assert "metadata" in payload
          assert "actions" in payload

      async def test_missing_metadata_defaults_to_empty_dict(self):
          state = make_state({"type": "text", "content": "Hello"})
          result = await format_for_web(state)
          payload = json.loads(result["formatted_response"])
          assert payload["metadata"] == {}

      async def test_missing_actions_defaults_to_empty_list(self):
          state = make_state({"type": "text", "content": "Hello"})
          result = await format_for_web(state)
          payload = json.loads(result["formatted_response"])
          assert payload["actions"] == []

      async def test_provided_metadata_is_preserved(self):
          state = make_state({
              "type": "appointment_card",
              "content": "Confirmed.",
              "metadata": {"doctor_name": "Dr. Mugisha"},
              "actions": ["confirm", "cancel"],
          })
          result = await format_for_web(state)
          payload = json.loads(result["formatted_response"])
          assert payload["metadata"]["doctor_name"] == "Dr. Mugisha"
          assert payload["actions"] == ["confirm", "cancel"]

      async def test_none_response_does_not_crash(self):
          state = make_state(response=None)
          result = await format_for_web(state)
          payload = json.loads(result["formatted_response"])
          assert "type" in payload
