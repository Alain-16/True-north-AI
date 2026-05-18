import pytest
from agent.state import AgentState
from agent.graph import route_intent, route_channel

  # ---------------------------------------------------------------------------
  # Helpers
  # ---------------------------------------------------------------------------

def make_state(current_flow=None, pending_intent=None, channel="web"):
      """Build a minimal state for routing tests — skips full validation."""
      return AgentState.model_construct(
          current_flow=current_flow,
          pending_intent=pending_intent,
          channel=channel,
      )


  # ---------------------------------------------------------------------------
  # route_intent
  # ---------------------------------------------------------------------------

class TestRouteIntent:

      @pytest.mark.parametrize("flow", ["booking", "triage", "reports", "queue", "reminders"])
      def test_main_flows_route_to_themselves(self, flow):
          state = make_state(current_flow=flow)
          assert route_intent(state) == flow

      def test_resume_flow_with_valid_pending_intent(self):
          state = make_state(
              current_flow="resume_flow",
              pending_intent={"flow": "booking", "flow_state": {"specialty": "dermatology"}},
          )
          assert route_intent(state) == "booking"

      @pytest.mark.parametrize("flow", ["booking", "triage", "reports", "queue", "reminders"])
      def test_resume_flow_restores_any_main_flow(self, flow):
          state = make_state(
              current_flow="resume_flow",
              pending_intent={"flow": flow, "flow_state": {}},
          )
          assert route_intent(state) == flow

      def test_resume_flow_with_no_pending_intent(self):
          state = make_state(current_flow="resume_flow", pending_intent=None)
          assert route_intent(state) == "graceful_fallback"

      def test_resume_flow_with_unrecognised_pending_flow(self):
          # Corrupt or stale pending_intent must not crash or misroute
          state = make_state(
              current_flow="resume_flow",
              pending_intent={"flow": "nonexistent_flow"},
          )
          assert route_intent(state) == "graceful_fallback"

      def test_resume_flow_with_empty_pending_intent_dict(self):
          state = make_state(
              current_flow="resume_flow",
              pending_intent={},  # flow key is missing entirely
          )
          assert route_intent(state) == "graceful_fallback"

      def test_unknown_intent_routes_to_fallback(self):
          state = make_state(current_flow="unknown")
          assert route_intent(state) == "graceful_fallback"

      def test_none_current_flow_routes_to_fallback(self):
          state = make_state(current_flow=None)
          assert route_intent(state) == "graceful_fallback"

      def test_arbitrary_string_routes_to_fallback(self):
          # Defensive: if classify_intent ever returns something unexpected,
          # routing must not raise — it must fall through cleanly
          state = make_state(current_flow="banana")
          assert route_intent(state) == "graceful_fallback"


  # ---------------------------------------------------------------------------
  # route_channel
  # ---------------------------------------------------------------------------

class TestRouteChannel:

      def test_whatsapp_routes_to_whatsapp_formatter(self):
          state = make_state(channel="whatsapp")
          assert route_channel(state) == "format_for_whatsapp"

      def test_web_routes_to_web_formatter(self):
          state = make_state(channel="web")
          assert route_channel(state) == "format_for_web"
