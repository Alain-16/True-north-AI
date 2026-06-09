import json
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from features.chat.router import router
from core.security import create_access_token

  # Minimal app — only the chat router, no lifespan, no DB connections
test_app = FastAPI()
test_app.include_router(router)

  # Identity now comes from a verified access token, not the request body.
PATIENT_ID = "patient-abc"
OPENMRS_ID = "OP-123"
AUTH = {"Authorization": f"Bearer {create_access_token(PATIENT_ID, OPENMRS_ID)}"}

PAYLOAD = {"message": "Book me a doctor"}


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
          response = await client.post("/chat/stream", json=PAYLOAD, headers=AUTH)
          assert response.headers["content-type"].startswith("text/event-stream")

      async def test_response_ends_with_done(self, client):
          response = await client.post("/chat/stream", json=PAYLOAD, headers=AUTH)
          data_lines = get_data_lines(response)
          assert data_lines, "No data lines found in SSE response"
          assert data_lines[-1] == "data: [DONE]"

      async def test_token_payload_is_valid_json(self, client):
          response = await client.post("/chat/stream", json=PAYLOAD, headers=AUTH)
          data_lines = get_data_lines(response)
          token_line = data_lines[0]
          payload = json.loads(token_line.removeprefix("data: "))
          assert "token" in payload

      async def test_token_contains_formatted_response(self, client):
          response = await client.post("/chat/stream", json=PAYLOAD, headers=AUTH)
          data_lines = get_data_lines(response)
          token_line = data_lines[0]
          payload = json.loads(token_line.removeprefix("data: "))
          inner = json.loads(payload["token"])
          assert inner["content"] == "Here to help."

      async def test_thread_id_derived_from_token(self):
          # thread_id must come from the TOKEN's patient id, not the body.
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
              await c.post("/chat/stream", json=PAYLOAD, headers=AUTH)

          assert captured["config"]["configurable"]["thread_id"] == f"{PATIENT_ID}:web"

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
              response = await c.post("/chat/stream", json=PAYLOAD, headers=AUTH)

          data_lines = get_data_lines(response)
          error_lines = [l for l in data_lines if "error" in l]
          assert error_lines, "No error event found in SSE response"
          assert data_lines[-1] == "data: [DONE]"

      async def test_missing_message_returns_422(self, client):
          # message is required; auth present so we reach validation.
          response = await client.post("/chat/stream", json={}, headers=AUTH)
          assert response.status_code == 422

      async def test_missing_auth_returns_401(self, client):
          # No bearer token → rejected before reaching the graph.
          response = await client.post("/chat/stream", json=PAYLOAD)
          assert response.status_code == 401

      async def test_bad_token_returns_401(self, client):
          response = await client.post(
              "/chat/stream", json=PAYLOAD, headers={"Authorization": "Bearer not.a.jwt"}
          )
          assert response.status_code == 401
