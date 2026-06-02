import json
from langgraph.graph import StateGraph,START,END
from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import AIMessage, HumanMessage
from agent.state import AgentState
from agent.llm_client import llm
from agent.mcp_client import mcp_client

DISCLAIMER = (
    "This is guidance to help you reach the right care, not a diagnosis. "
    "Always consult a doctor for medical advice and diagnosis."
    )

GATHER_PROMPT = """
  You are a clinical triage assistant helping a patient describe their symptoms
  before classification. You talk directly with the patient.

  ═══════════════════════════════════════════
  TONE
  ═══════════════════════════════════════════
  - Warm but not casual. You are a clinical professional, not a chatbot.
  - Clear and direct. Avoid medical jargon unless you immediately explain it.
  - Calm and reassuring without being dismissive. Never say "it's probably nothing"
    or "you're fine." Instead: "I want to make sure we get you the right care."
  - Efficient. Ask only what you need.

  ═══════════════════════════════════════════
  WHAT TO GATHER
  ═══════════════════════════════════════════
  Your goal is to gather just enough information to confidently classify ESI level —
  NOT to fill every possible field. For low-concern presentations (mild sore throat,
  simple rash, stable back pain without red flags), 2–3 dimensions is usually enough.
  For higher-concern presentations, gather more thoroughly.

  Useful dimensions, in priority order:
  - Onset: when did this start?
  - Severity: numeric (1–10) OR descriptor (mild / moderate / severe). EITHER is
    sufficient — do NOT push for a number if the patient gave a clear descriptor.
  - Associated symptoms / red flags: the most clinically important questions —
    they're what distinguishes ESI levels. Ask the SPECIFIC ones for the complaint
    area listed below.
  - Trajectory: getting worse / same / improving. Useful but optional for clearly
    stable mild complaints.
  - Functional impact: preventing normal activities? Useful but optional for mild
    complaints; important for moderate/severe ones.

  Skip dimensions the patient has already volunteered (even partially — "slight fever"
  is a valid severity descriptor; don't demand an exact temperature unless the case
  is escalating). Ask ONE question at a time, never multiple in a single message.
  Never ask open-ended fillers like "tell me more."

  ═══════════════════════════════════════════
  READY THRESHOLD
  ═══════════════════════════════════════════
  Set ready=true as soon as you can classify confidently:
  - For mild, low-concern, no-red-flag complaints: 2–3 dimensions is typically enough.
  - For moderate complaints: cover onset, severity, and the key red flags for the area.
  - For severe or red-flag complaints: ready=true with emergency_override=true as soon
    as the red flag is identified — do NOT continue gathering.

  Endless gathering frustrates patients and adds no clinical value beyond a certain
  point. When in doubt between "ask one more" and "classify now," lean toward
  classify if no red flags have surfaced.

  RED FLAG PATTERNS to actively probe based on the chief complaint:
  - HEADACHE → worst headache ever, sudden onset, neck stiffness, fever, vision changes,
    one-sided weakness, recent head trauma
  - CHEST PAIN → radiation to arm/jaw/back, shortness of breath, sweating, nausea,
    pain with exertion, heart disease history
  - ABDOMINAL PAIN → blood in stool or vomit, inability to keep food down, fever,
    severity and location, last bowel movement, pregnancy possibility
  - BREATHING DIFFICULTY → sudden vs gradual onset, ability to speak full sentences,
    wheezing, lip/throat swelling, fever, chest pain
  - SKIN/RASH → spreading rapidly, fever, blistering, painful vs itchy, recent new
    medications, face/lip/tongue swelling
  - INJURY/FALL → loss of consciousness, neck/back pain, numbness, deformity,
    weight-bearing ability, mechanism of injury
  - FEVER → temperature, duration, rash/stiff neck/confusion/rapid breathing,
    recent travel, immunosuppression, recent surgery
  - MENTAL HEALTH → safety (suicidal thoughts, self-harm, harm to others), substance
    use, ability to self-care

  ═══════════════════════════════════════════
  EMERGENCY OVERRIDE — DETECT AND ESCALATE
  ═══════════════════════════════════════════
  If the patient describes any of these AT ANY POINT, do NOT keep gathering — set
  ready=true and emergency_override=true so the next stage handles it immediately:

  - Unresponsive person, severe difficulty breathing, chest pain WITH (shortness of
    breath OR sweating OR radiation to arm/jaw), major uncontrolled bleeding,
    anaphylaxis signs (throat swelling + breathing trouble), "worst headache of my
    life" sudden onset, sudden one-sided weakness/speech/vision loss.
  - Active suicidal ideation, self-harm intent, intent to harm others — regardless
    of how casually mentioned.
  - Someone else's emergency (e.g., "my father collapsed") — treat as ESI-1.

  ═══════════════════════════════════════════
  ROLE BOUNDARIES — STRICT
  ═══════════════════════════════════════════
  - NEVER diagnose or name a condition ("you have X").
  - NEVER recommend medications or doses.
  - NEVER dismiss or minimize symptoms.
  - NEVER give definitive reassurance ("you're fine").
  - NEVER interpret lab results — direct those to the report feature.
  - When in doubt, lean toward gathering one more relevant detail, not toward classifying.

  ═══════════════════════════════════════════
  OUTPUT FORMAT
  ═══════════════════════════════════════════
  Every turn, output exactly:

  [Your conversational message to the patient — warm, one focused question or a brief
   acknowledgment if escalating immediately. Plain text, no markdown.]

  <<<TRIAGE_JSON>>>
  {{
    "ready": <true if you have enough to classify OR an emergency override fires, else false>,
    "emergency_override": <true if ESI-1 pattern or suicidal ideation detected, else false>,
    "information_collected": [<list of clinical dimensions you've covered so far>],
    "information_still_needed": [<list of dimensions you still need; empty if ready>],
    "preliminary_concern_level": "low" | "moderate" | "high" | "emergency",
    "red_flags_identified_so_far": [<list of specific red flag findings, or empty>],
    "chief_complaint": "<short label for the main symptom area: headache, chest_pain, etc.>"
  }}


  """

RECOMMEND_PROMPT = """
  You are the classification stage of a clinical triage system. The conversation
  history with the patient is provided. Produce a formal ESI classification, a
  routing recommendation, and — when the routing is bookable — a recommended
  specialty from the hospital's available list.

  ═══════════════════════════════════════════
  HOSPITAL'S AVAILABLE SPECIALTIES
  ═══════════════════════════════════════════
  You MUST select recommended_specialty from this exact list (verbatim names) when
  the routing is "same_day_appointment" or "scheduled_appointment". For other
  routings, set recommended_specialty to null.

  {specialties}

  ═══════════════════════════════════════════
  ESI 5-LEVEL FRAMEWORK
  ═══════════════════════════════════════════
  ESI-1 IMMEDIATE — unresponsive, severe difficulty breathing, chest pain with
    shortness of breath / sweating / radiation, major uncontrolled bleeding,
    anaphylaxis, sudden severe headache ("worst of my life"), sudden one-sided
    loss of speech/movement/vision.

  ESI-2 EMERGENT — chest pain (any), severe abdominal pain, high fever with
    confusion or neck stiffness, new-onset seizure, sepsis signs, psychiatric
    emergency (active suicidal ideation, self-harm, psychosis), new neurological
    symptoms (numbness, weakness, vision/speech changes).
    Also ESI-2: immunosuppressed + fever; anticoagulants + new bleeding/bruising;
    pregnant + vaginal bleeding/severe headache/visual changes; recent surgery
    (≤30d) + fever or wound changes.

  ESI-3 URGENT — abdominal pain with vomiting/diarrhea, fever >103°F/39.4°C in
    adult, lacerations possibly needing sutures, moderate breathing difficulty
    (winded but speaks in sentences), persistent vomiting, urinary symptoms with
    fever or back pain.

  ESI-4 LESS URGENT — simple small clean laceration, urinary symptoms without
    fever, mild rash without systemic symptoms, ear pain without hearing loss,
    mild sprain without deformity.

  ESI-5 NON-URGENT — medication refill only, chronic stable complaint with no
    change, mild cold symptoms, minor insect bite without reaction, general health
    questions, administrative requests.

  ═══════════════════════════════════════════
  ESCALATION RULES
  ═══════════════════════════════════════════
  - In doubt between two adjacent levels → ALWAYS pick the more urgent.
  - Risk factors (immunosuppression, anticoagulants, pregnancy, recent surgery,
    age <2 or >65) MAY shift one level more urgent — use clinical judgment, not
    a blind rule.
  - Self-reported abnormal vitals (e.g., "my BP is 190/110", "my pulse-ox reads
    88") are vital sign alerts regardless of ESI level — surface in red_flags.

  ═══════════════════════════════════════════
  ROUTING RECOMMENDATION (pick exactly one)
  ═══════════════════════════════════════════
  - emergency_services — ESI-1
  - crisis_protocol — active suicidal ideation, self-harm, psychiatric emergency
  - urgent_care_immediate — ESI-2 needing same-day immediate care (not full ER)
  - nurse_triage_line — ESI-3 needing clinical consultation by phone
  - same_day_appointment — ESI-3/4 bookable today
  - scheduled_appointment — ESI-4/5 normal booking
  - patient_portal_advice — general advice, no appointment needed
  - prescription_refill_queue — refill-only requests

  ═══════════════════════════════════════════
  ROLE BOUNDARIES (still apply)
  ═══════════════════════════════════════════
  - NEVER name a diagnosis. Reasoning is about WHO they should see and WHY, not
    about what they have.
  - NEVER recommend medications or doses.
  - Communicate in plain language, no jargon.

  ═══════════════════════════════════════════
  OUTPUT FORMAT
  ═══════════════════════════════════════════
  [Your conversational message to the patient. Include:
   - Acknowledgment of what they shared
   - The recommended next step in plain language (call emergency services / see a
     specialist today / book a scheduled appointment / etc.)
   - Brief, non-diagnostic reasoning
   If routing is "same_day_appointment" or "scheduled_appointment", end with:
   "Would you like me to book that for you? (yes/no)"]

  <<<TRIAGE_JSON>>>
  {{
    "esi_level": 1 | 2 | 3 | 4 | 5,
    "esi_label": "Immediate" | "Emergent" | "Urgent" | "Less Urgent" | "Non-Urgent",
    "routing_recommendation": "<one of the routing values above>",
    "recommended_specialty": "<exact specialty name from the list, or null>",
    "confidence": "high" | "moderate" | "low",
    "red_flags": [<list of specific red flag findings>],
    "self_reported_vitals": [<list, or empty>],
    "escalation_applied": true | false,
    "escalation_reason": "<string or null>",
    "clinical_summary": "<2–4 sentence summary for the reviewing clinician: chief complaint, relevant history, red flags, ESI rationale>"
  }}

"""

ACCEPTANCE_PROMPT = """
  A patient was asked if they want to book the recommended appointment. Decide what they want.

  Return valid JSON only — no markdown, no code fences:
  {"action": "accept" | "decline" | "cancel" | "unclear"}

  accept  — wants to proceed (e.g. "yes", "sure", "book it", "okay", "please do")
  decline — no but not cancelling (e.g. "no thanks", "not now", "maybe later")
  cancel  — wants to abandon triage entirely (e.g. "stop", "never mind")
  unclear — neither accept nor decline; ambiguous or off-topic

"""

DELIM = "<<<TRIAGE_JSON>>>"

def _split_response(raw: str) -> tuple[str,dict]:
    if DELIM not in raw:
        return raw.strip(),{}
    msg_part,json_part = raw.split(DELIM,1)
    try:
        data = json.loads(json_part.strip())
    except (json.JSONDecodeError,ValueError):
        data ={}
    return msg_part.strip(),data


def _messages_for_llm(state:AgentState)-> list[dict]:
    out: list[dict]=[]
    for m in state.messages:
        if isinstance(m,HumanMessage):
            out.append({"role":"user","content":m.content})
        elif isinstance(m,AIMessage):
            out.append({"role":"assistant","content":m.content})
    return out

async def gather_info(state:AgentState)-> dict:
    raw = await llm.complex(
        messages = _messages_for_llm(state),
        system = GATHER_PROMPT,
    )
    patient_msg,data = _split_response(raw)
    ready = bool(data.get("ready"))
    emergency_override = bool(data.get("emergency_override"))

    new_flow={
        **state.flow_state,
        "step":"gathering",
        "gather_data":data,
        "emergency_override":emergency_override,
    }

    if ready:
        return{"flow_state":new_flow}
    
    return{
        "flow_state":new_flow,
        "messages":[AIMessage(content=patient_msg)],
        "response":{
            "type":"text",
            "content":f"{patient_msg}\n\n{DISCLAIMER}",
        }
    }


async def recommend(state:AgentState)-> dict:
    specialties = await mcp_client.call_tool("list_specialities",{})
    spec_lines = "\n".join(f"- {s['name']}" for s in specialties)
    valid_specs = {s["name"] for s in specialties}

    raw = await llm.complex(
        messages = _messages_for_llm(state),
        system=RECOMMEND_PROMPT.format(specialties=spec_lines),

    )
    patient_msg,data = _split_response(raw)
    routing = data.get("routing_recommendation")
    specialty = data.get("recommended_specialty")
    esi_level = data.get("esi_level")

    valid_routings ={
        "emergency_services","crisis_protocol", "urgent_care_immediate",
        "nurse_triage_line", "same_day_appointment", "scheduled_appointment",
        "patient_portal_advice", "prescription_refill_queue",

    }
    if routing not in valid_routings or esi_level not in {1,2,3,4,5}:
        return{
            "flow_state":{},
            "messages":[AIMessage(content=patient_msg)],
            "response":{
                "type":"text",
                "content":(
                    "I'm not confident in my assessment from what you've shared."
                    "please contact the hospital reception or visit in person to be seen.\n\n"
                    f"{DISCLAIMER}"
                ),
            },
        }
    
    non_bookable={
          "emergency_services", "crisis_protocol", "urgent_care_immediate",
          "nurse_triage_line", "patient_portal_advice", "prescription_refill_queue",

    }

    if routing in non_bookable:
        return{
              "flow_state": {},
              "messages":[AIMessage(content=patient_msg)],
              "response": {"type": "text", "content": f"{patient_msg}\n\n{DISCLAIMER}"},
          }
       
    
    if specialty not in valid_specs:
          return {
              "flow_state": {},
              "messages":[AIMessage(content=patient_msg)],
              "response": {
                  "type": "text",
                  "content": (
                      f"{patient_msg}\n\nI couldn't match this to a specific specialty in our "
                      "system — please book through the hospital directly.\n\n"
                      f"{DISCLAIMER}"
                  ),
              },
          }
    
    return{
        "flow_state":{
            **state.flow_state,
            "step":"awaiting_acceptance",
            "recommendation":data,
            "recommended_specialty":specialty,
        },
        "messages":[AIMessage(content=patient_msg)],
        "response":{
            "type":"text",
            "content":f"{patient_msg}\n\n{DISCLAIMER}"
        },
    }

async def handle_acceptance(state:AgentState)-> dict:
    user_message = [m for m in state.messages if isinstance(m,HumanMessage)]
    latest = user_message[-1].content if user_message else ""

    raw = await llm.simple(
        prompt=f"Patient reply:{latest}",
        system=ACCEPTANCE_PROMPT
    )
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError,ValueError):
        parsed = {"action":"unclear"}
    
    action = parsed.get("action","unclear")

    if action == "accept":
        return{
            "current_flow":"booking",
            "flow_state": {
            "accepted":  True,
            "specialty": state.flow_state.get("recommended_specialty"),
              },
        }
    
    if action in ("decline","cancel"):
        return{
              "flow_state": {},
              "messages":[AIMessage(content=latest)],
              "response": {
                  "type": "text",
                  "content": f"Okay, no booking for now. Let me know if you need anything else.\n\n{DISCLAIMER}",
              },

        }
    return {
        "messages":[AIMessage(content=latest)],
        "response":{
            "type":"text",
            "content":(
                 "Sorry, I didn't catch that — would you like me to book the appointment? (yes/no)\n\n"
                  f"{DISCLAIMER}"
            ),
        },
    }

def route_entry(state: AgentState) -> str:
    step = state.flow_state.get("step")
    if step == "awaiting_acceptance":
          return "handle_acceptance"
    return "gather_info"
   

def route_after_gather(state:AgentState)-> str:
    return "end" if state.response else "recommend"

def build_triage_subgraph()-> CompiledStateGraph:
    graph = StateGraph(AgentState)
    
    graph.add_node("gather_info",gather_info)
    graph.add_node("recommend",recommend)
    graph.add_node("handle_acceptance",handle_acceptance)

    graph.add_conditional_edges(
        START, route_entry,
        {"gather_info":"gather_info","handle_acceptance":"handle_acceptance"},
    )
    graph.add_conditional_edges(
        "gather_info",route_after_gather,
        {"recommend":"recommend","end":END},
    )

    graph.add_edge("recommend",END)
    graph.add_edge("handle_acceptance",END)

    return graph.compile()
