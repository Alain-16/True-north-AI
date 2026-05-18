import json
import re
from agent.state import AgentState

_MARKDOWN_PATTERNS = [
    (r'\*\*(.*?)\*\*', r'\1'),   # **bold**
    (r'\*(.*?)\*',     r'\1'),   # *italic*
    (r'_(.*?)_',       r'\1'),   # _italic_
    (r'#{1,6}\s+',     r''),     # ## headers
    (r'`{1,3}.*?`{1,3}', r'', ), # `code` and ```blocks```

]

def _strip_markdown(text:str)->str:
    for pattern,replacement in _MARKDOWN_PATTERNS:
        text = re.sub(pattern,replacement,text,flags=re.DOTALL)

    return text.strip()

_WHATSAPP_LIMIT = 1600
_DEFAULT_RESPONSE = {"type":"text","content":"I'm here to help. What would you like to do?"}

async def format_for_whatsapp(state:AgentState)-> dict:
    response = state.response or _DEFAULT_RESPONSE
    msg_type = response.get("type","text")
    content = response.get("content","")
    meta = response.get("metadata",{})

    if msg_type == "appointment_card":
        text = (
            f"Booked \u2713\n"
            f"Doctor: {meta.get('doctor_name', 'TBD')}\n"
            f"Specialty: {meta.get('specialty', 'TBD')}\n"
            f"Date: {meta.get('scheduled_at', 'TBD')}\n\n"
            f"{content}"

        )
    elif msg_type == "queue_status":
        text =(
            f"Queue position: #{meta.get('position', '?')}\n"
            f"Estimated wait: {meta.get('wait_minutes', '?')} minutes\n\n"
            f"{content}"

        )
    elif msg_type == "triage_result":
        urgency = meta.get("urgency","routine").upper()
        text = f"Triage result({urgency}):\n\n{content}"
    elif msg_type == "lab_result":
        text = f"Lab result:\n\n{content}"
    else:
        text = content
    
    text = _strip_markdown(text)

    if len(text)>_WHATSAPP_LIMIT:
        text = text[:_WHATSAPP_LIMIT-3] + "..."
    return {"formatted_response":text}

async def format_for_web(state:AgentState):
    response = state.response or _DEFAULT_RESPONSE

    web_payload ={
        "type": response.get("type","text"),
        "content": response.get("content",""),
        "metadata": response.get("metadata",{}),
        "actions": response.get("actions",[]),
    }
    return {"formatted_response":json.dumps(web_payload)}