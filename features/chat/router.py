import json
from fastapi import APIRouter,Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from agent.state import AgentState

router = APIRouter(prefix="/chat",tags=["chat"])

class ChatRequest(BaseModel):
    message:str
    patient_id:str
    openmrs_patient_id:str

async def _event_stream(graph,initial_state:dict, config:dict):
    try:
        async for node_updates in graph.astream(initial_state,config):
            for node_output in node_updates.values():
                formatted = node_output.get("formatted_response")
                if formatted:
                    yield f"data: {json.dumps({'token':formatted})}\n\n"
    except Exception:
        yield f"data: {json.dumps({'error': 'Something went wrong. Please try again.'})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


@router.post("/stream")
async def chat_stream(body: ChatRequest, req: Request) -> StreamingResponse:
      graph = req.app.state.graph

      # One stable thread per patient per channel — derived, never client-supplied
      thread_id = f"{body.patient_id}:web"

      initial_state = {
          "messages":           [HumanMessage(content=body.message)],
          "patient_id":         body.patient_id,
          "openmrs_patient_id": body.openmrs_patient_id,
          "channel":            "web",
      }

      config = {"configurable": {"thread_id": thread_id}}

      return StreamingResponse(
          _event_stream(graph, initial_state, config),
          media_type="text/event-stream",
          headers={
              # Prevent proxies and Nginx from buffering the stream
              "Cache-Control": "no-cache",
              "X-Accel-Buffering": "no",
          },
      )
