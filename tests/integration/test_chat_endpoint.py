import json
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from features.chat.router import router

  # Minimal app — only the chat router, no lifespan, no DB connections
test_app = FastAPI()
test_app.include_router(router)

PAYLOAD = {
      "message": "Book me a doctor",
      "patient_id": "patient-abc",
      "openmrs_patient_id": "OP-123",
  }


  # ---------------------------------------------------------------------------
  # Helpers
  # ---------------------------------------------------------------------------

def make_fake_stream(formatted_response: str):
      """Returns an async generator function that yields one node update."""
      async def _stream(*args, **kwargs):
          yield {"format_for_web": {"formatted_response": formatted_response}}
      return _stream


def get_data_lines(response) -> list[str]:
      return [l for l in response.text.splitlines() if l.startswith("data: ")]


  # ---------------------------------------------------------------------------
  # Fixtures
  # ---------------------------------------------------------------------------

@pytest.fixture
async def client():
      mock_graph = MagicMock()
      mock_graph.astream = make_fake_stream('{"type":"text","content":"Here to help."}')
      test_app.state.graph = mock_graph

      async with AsyncClient(
          transport=ASGITransport(app=test_app), base_url="http://test"
      ) as c:
          yield c


  # ---------------------------------------------------------------------------
  # Tests
  # ---------------------------------------------------------------------------

class TestChatStreamEndpoint:

      async def test_content_type_is_event_stream(self, client):
          response = await client.post("/chat/stream", json=PAYLOAD)
          assert response.headers["content-type"].startswith("text/event-stream")

      async def test_response_ends_with_done(self, client):
          response = await client.post("/chat/stream", json=PAYLOAD)
          data_lines = get_data_lines(response)
          assert data_lines, "No data lines found in SSE response"
          assert data_lines[-1] == "data: [DONE]"

      async def test_token_payload_is_valid_json(self, client):
          response = await client.post("/chat/stream", json=PAYLOAD)
          data_lines = get_data_lines(response)
          # First data line is the token; last is [DONE]
          token_line = data_lines[0]
          payload = json.loads(token_line.removeprefix("data: "))
          assert "token" in payload

      async def test_token_contains_formatted_response(self, client):
          response = await client.post("/chat/stream", json=PAYLOAD)
          data_lines = get_data_lines(response)
          token_line = data_lines[0]
          payload = json.loads(token_line.removeprefix("data: "))
          inner = json.loads(payload["token"])
          assert inner["content"] == "Here to help."

      async def test_thread_id_derived_from_patient_id(self):
          # Track what config astream was called with
          captured = {}

          async def tracking_stream(*args, **kwargs):
              captured["config"] = args[1] if len(args) > 1 else kwargs.get("config")
              yield {"format_for_web": {"formatted_response": '{"type":"text","content":"ok"}'}}

          mock_graph = MagicMock()
          mock_graph.astream = tracking_stream
          test_app.state.graph = mock_graph

          async with AsyncClient(
              transport=ASGITransport(app=test_app), base_url="http://test"
          ) as c:
              await c.post("/chat/stream", json=PAYLOAD)

          expected_thread_id = f"{PAYLOAD['patient_id']}:web"
          assert captured["config"]["configurable"]["thread_id"] == expected_thread_id

      async def test_graph_error_produces_error_event(self):
          async def error_stream(*args, **kwargs):
              raise RuntimeError("FHIR unavailable")
              yield  # makes this a generator function

          mock_graph = MagicMock()
          mock_graph.astream = error_stream
          test_app.state.graph = mock_graph

          async with AsyncClient(
              transport=ASGITransport(app=test_app), base_url="http://test"
          ) as c:
              response = await c.post("/chat/stream", json=PAYLOAD)

          data_lines = get_data_lines(response)
          # Error event must appear
          error_lines = [l for l in data_lines if "error" in l]
          assert error_lines, "No error event found in SSE response"
          # [DONE] must still appear — finally block must have run
          assert data_lines[-1] == "data: [DONE]"

      async def test_missing_required_field_returns_422(self, client):
          # Pydantic validation — patient_id is required
          response = await client.post("/chat/stream", json={"message": "hello"})
          assert response.status_code == 422
