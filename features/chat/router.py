import json
from fastapi import APIRouter,Request,Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from agent.state import AgentState
from features.auth.deps import get_current_patient

router = APIRouter(prefix="/chat",tags=["chat"])

class ChatRequest(BaseModel):
    message:str
    # Optional: when the patient is asking a follow-up about a specific delivered
    # report, the web client sends its report_delivery_log id. Routes to report_qa.
    report_id: str | None = None

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
async def chat_stream(body: ChatRequest, req: Request,
                      patient: dict = Depends(get_current_patient)) -> StreamingResponse:
      graph = req.app.state.graph

      # Identity comes from the verified access token, never the request body.
      patient_id = patient["patient_id"]
      thread_id = f"{patient_id}:web"

      initial_state = {
          "messages":           [HumanMessage(content=body.message)],
          "patient_id":         patient_id,
          "openmrs_patient_id": patient["openmrs_patient_id"],
          "channel":            "web",
          # Always set (None clears it) so prior report context doesn't persist
          # in the checkpoint after the patient leaves the report Q&A.
          "report_id":          body.report_id,
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
