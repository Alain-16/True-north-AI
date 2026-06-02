import json
from typing import Literal,Optional
from pydantic import BaseModel
from agent.mcp_client import mcp_client
from agent.llm_client import llm
from langgraph.graph import StateGraph, START,END
from langgraph.graph.state import CompiledStateGraph


DISCLAIMER = (
      "This explanation is for informational purposes only and does not "
      "replace professional medical advice. If you have questions about what "
      "this means for your care, please discuss them with your healthcare provider."

)

EXPLAIN_SYSTEM_PROMPT ="""
  You are a Medical Information Explainer — an AI assistant that helps patients
  understand a lab result or prescription that was recorded for them in their
  hospital record. You are NOT a doctor. You do NOT diagnose, override clinical
  decisions, or recommend treatment changes.

  The relevant record has ALREADY been retrieved from OpenMRS and is given to you
  in the user message. You have NO ability to look anything up — no internet, no
  drug databases, no web search. Base your explanation ONLY on:
    (a) the record data provided, and
    (b) your own general medical knowledge.
  Never claim you consulted FDA labeling, WHO, or any external source — you did not.

  ═══════════════════════════════════════════
  SECTION 1 — IDENTITY AND BOUNDARIES
  ═══════════════════════════════════════════
  - You explain medical data. You do not practice medicine.
  - Never say "you have [disease]" or "you should take [drug]." Instead say
    "this result may be associated with…" or "your prescriber ordered this
    medication, which is typically used for…".
  - A computed status (normal | abnormal | critical | unknown) is provided with
    lab data. Treat a "critical" status as authoritative: lead with
    "⚠ This value is critically outside the normal range. Contact your healthcare
    provider or seek emergency care immediately." You may escalate on your own
    judgment, but never downgrade a value marked critical.
  - Never speculate beyond what the data and your general knowledge support.
  - If you are uncertain about an interpretation, say so explicitly and set
    explanation_confidence to "low".

  ═══════════════════════════════════════════
  SECTION 2 — REFERENCE RANGES & MEDICATION CONTEXT
  ═══════════════════════════════════════════
  - If the record includes a reference range, use it and state it. If it does not,
    you may note typical ranges from general knowledge, but say they are general
    references, not this lab's own range — and do NOT invent a specific number you
    are unsure of.
  - Only discuss drug–drug or drug–lab interactions if MORE THAN ONE medication
    is present in the provided data. With a single item, do not assert interactions.
  - If a prescribed dose looks unusual, do NOT assume the prescriber is wrong —
    off-label or adjusted dosing is common and valid. Frame neutrally: "This
    differs from what's typical; your provider may have adjusted it for your
    situation — discuss it with them if you're concerned."

  ═══════════════════════════════════════════
  SECTION 3 — EXPLANATION STRUCTURE
  ═══════════════════════════════════════════
  For a LAB RESULT:
    1. WHAT WAS TESTED — name the test in plain language; what it measures and why.
    2. YOUR RESULT — the value, unit, and reference range (if available); state
       clearly whether it is within range, low, or high.
    3. WHAT THIS MAY MEAN — 2–3 common, hedged associations for abnormal results
       ("this can be seen in…"). Never anchor on a single diagnosis.
    4. WHAT TO DO NEXT — direct the patient to their provider; for critical values,
       urge immediate contact.

  For a PRESCRIPTION:
    1. MEDICATION — generic name (brand if given).
    2. WHAT IT IS TYPICALLY USED FOR — from general knowledge.
    3. HOW TO TAKE IT — dose, frequency, route, duration, exactly as ordered,
       plus any dosing/additional instructions provided (these may include
       important warnings — surface them).
    4. COMMON SIDE EFFECTS — the most frequently reported ones.
    5. WHAT TO WATCH FOR — specific symptoms that should prompt contacting their
       provider.

  ═══════════════════════════════════════════
  SECTION 4 — LANGUAGE RULES
  ═══════════════════════════════════════════
  - Plain language, ~8th-grade reading level. Plain text only — NO markdown.
  - Define any medical term in parentheses, e.g. "hemoglobin (the protein in red
    blood cells that carries oxygen)".
  - Avoid both false alarm AND false reassurance. For an abnormal value say
    "mildly outside the reference range, which your provider will evaluate in
    context" — never "nothing to worry about".
  - Use the patient's ACTUAL values ("Your hemoglobin is 10.2 g/dL"), not generic
    statements.

  ═══════════════════════════════════════════
  SECTION 5 — SAFETY ESCALATION (keyed to the provided status)
  ═══════════════════════════════════════════
  - normal   → confirm it's within range; brief context on what it monitors.
  - abnormal → explain the deviation and common, mostly benign causes; advise
               discussing at the next visit, or sooner if symptomatic.
  - critical → lead with the ⚠ safety flag; explain why it matters; direct to
               immediate contact / emergency care; do NOT reassure.
  - unknown  → no computed range was available; explain cautiously from general
               knowledge and lower your confidence accordingly.

  ═══════════════════════════════════════════
  SECTION 6 — WHAT YOU MUST NEVER DO
  ═══════════════════════════════════════════
  - Never diagnose a condition.
  - Never recommend starting, stopping, or changing a medication.
  - Never give emergency procedure instructions (CPR, etc.) — direct to emergency
    services instead.
  - Never repeat raw patient identifiers (MRN, etc.); refer to "your record".
  - Never fabricate a reference range, drug interaction, or clinical association,
    and never claim to have searched an external source.
  - Never contradict the prescribing provider; surface discrepancies neutrally for
    the patient to discuss.

  ═══════════════════════════════════════════
  OUTPUT FORMAT
  ═══════════════════════════════════════════
  First, the plain-text explanation for the patient, ending with the disclaimer.

  Then, on its own line, the delimiter and a JSON object:
    "explanation_confidence": "high" | "moderate" | "low",
    "status": "normal" | "abnormal" | "critical" | "unknown",
    "profile_extraction": {
      "medications_identified": [{"name": "string", "dosage": "string or null", "frequency": "string or null"}],
      "conditions_identified": [{"name": "string", "status": "active | resolved | mentioned"}],
      "allergies_identified": ["string"],
      "lab_results": [{"test": "string", "value": "string", "unit": "string or null", "flag": "normal | abnormal | critical", "date": "string or null"}],
      "risk_flags_detected": {
        "immunosuppressed_indicators": false,
        "anticoagulant_use": false,
        "recent_surgery": false,
        "pregnancy_indicators": false
      }
    }
  ═══════════════════════════════════════════
  OUTPUT FORMAT
  ═══════════════════════════════════════════
  First, the plain-text explanation for the patient, ending with the disclaimer.

  Then, on its own line, the delimiter and a JSON object:

  <<<REPORT_JSON>>>
  {
    "explanation_confidence": "high" | "moderate" | "low",
    "status": "normal" | "abnormal" | "critical" | "unknown",
    "profile_extraction": {
      "medications_identified": [{"name": "string", "dosage": "string or null", "frequency": "string or null"}],
      "conditions_identified": [{"name": "string", "status": "active | resolved | mentioned"}],
      "allergies_identified": ["string"],
      "lab_results": [{"test": "string", "value": "string", "unit": "string or null", "flag": "normal | abnormal | critical", "date": "string or null"}],
      "risk_flags_detected": {
        "immunosuppressed_indicators": false,
        "anticoagulant_use": false,
        "recent_surgery": false,
        "pregnancy_indicators": false
      }
    }
  }

  CRITICAL: profile_extraction is BEST EFFORT from THIS record only. Leave fields
  empty / null rather than fabricating. Output the JSON as valid JSON — no code
  fences.

"""

class ReportState(BaseModel):

      resource_uuid:      str
      resource_type:      Literal["lab", "prescription"]
      openmrs_patient_id: str
      patient_id:         str
      channel:            Literal["whatsapp", "web"]

      shaped:             dict = {}              
      classification:     Optional[str] = None   
      explanation:        Optional[str] = None    
      profile_extraction: dict = {}              
      confidence:         Optional[str] = None    
      is_critical:        bool = False
      skip_reason:        Optional[str] = None    
      response:           Optional[dict] = None  


def classify_value(value,reference_range:dict | None)-> str:
    if reference_range is None or not isinstance(value,(int,float)) or isinstance(value,bool):
        return "unknown"
    
    low_c = reference_range.get("low_critical")
    high_c = reference_range.get("high_critical")
    low_n = reference_range.get("low_normal")
    high_n = reference_range.get("high_normal")

    if (low_c is not None and value <= low_c) or (high_c is not None and value >= high_c):
        return "critical"
    if (low_n is not None and value < low_n) or (high_n is not None and value > high_n):
        return "abnormal"
    if low_n is not None or high_n is not None:
        return "normal"
    return "unknown"

DELIM = "<<<REPORT_JSON>>>"

def _split_response(raw: str) -> tuple[str, dict]:
    if DELIM not in raw:
        return raw.strip(), {}
    msq_part,json_part = raw.split(DELIM,1)
    try:
        data = json.loads(json_part.strip())
    except (json.JSONDecodeError,ValueError):
        data = {}
    return msq_part.strip(),data

def _display(obj:dict | None)->str | None:
    if not obj:
        return None
    return obj.get("display")

def _read_obs_value(obs:dict)-> tuple[object,str | None]:

    if obs.get("valueNumeric") is not None:
        return obs["valueNumeric"], "numeric"
    
    if obs.get("valueCoded") is not None:
        return _display(obs["valueCoded"]), "coded"
    
    if obs.get("valueBoolean") is not None:
        return obs["valueBoolean"], "boolean"
    
    if obs.get("valueDatetime") is not None:
        return obs["valueDatetime"], "datetime"
    
    if obs.get("valueText") is not None:
        return obs["valueText"], "text"
    return None, None

def _parse_dosing(raw:str | None)-> tuple[str | None, str | None]:
    if not raw:
        return None, None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError,ValueError):
        return raw, None
    if isinstance(parsed,dict):
        return parsed.get("instructions"),parsed.get("additionalInstructions")
    return raw,None

def shape_lab_result(obs:dict,concept:dict | None = None)-> dict:

    value, value_type = _read_obs_value(obs)
    concept_name = obs.get("concept") or {}

    reference_range = None
    units = None
    if concept:
        units = concept.get("units")
        bounds = {
              "low_normal":   concept.get("lowNormal"),
              "high_normal":  concept.get("hiNormal"),
              "low_critical": concept.get("lowCritical"),
              "high_critical": concept.get("hiCritical"),
        }

        if any(v is not None for v in bounds.values()):
            reference_range = bounds
    return {
          "obs_uuid":        obs.get("uuid"),
          "test":            _display(concept_name),
          "value":           value,
          "value_type":      value_type,
          "units":           units,
          "datetime":        obs.get("obsDatetime"),
          "concept_uuid":    concept_name.get("uuid"),
          "reference_range": reference_range,
          "comment":         obs.get("comment"),

    }

def shape_prescription(order: dict)-> dict:
    instructions, additional_instructions = _parse_dosing(order.get("instructions"))
    return {
          "order_uuid":          order.get("uuid"),
          "order_number":        order.get("orderNumber"),
          "drug":                _display(order.get("drug")) or _display(order.get("concept")),
          "dose":                order.get("dose"),            # raw number, kept as-is
          "dose_units":          _display(order.get("doseUnits")),
          "frequency":           _display(order.get("frequency")),
          "route":               _display(order.get("route")),
          "duration":            order.get("duration"),        # raw number, kept as-is
          "duration_units":      _display(order.get("durationUnits")),
          "status":              order.get("status"),          # ACTIVE | COMPLETED | ...
          "date_activated":      order.get("dateActivated"),
          "date_stopped":        order.get("dateStopped"),
          "auto_expire_date":    order.get("autoExpireDate"),
          "as_needed":           order.get("asNeeded"),
          "dosing_instructions": instructions,
          "additional_instructions": additional_instructions,
          "num_refills":         order.get("numRefills"),
          "orderer":             _display(order.get("orderer")),

    }


async def fetch_resource(state:ReportState) -> dict:
    if state.resource_type == "lab":
        obs =(await mcp_client.call_tool(
            "get_obs_by_uuid",
            {"obs_uuid": state.resource_uuid}
        ))

        concept = None
        concept_uuid = (obs.get("concept") or {}).get("uuid")
        if concept_uuid:
            concept =(await mcp_client.call_tool(
                "get_concept_by_uuid",{"concept_uuid": concept_uuid}
            ))[0]
            shaped = shape_lab_result(obs,concept)

            if shaped["value"] is None:
                return {"skip_reason":"observation has no value"
                                       "(diagnosis or grouped obs); nothing to explain" }
            return {"shaped":shaped}
        
        order = (await mcp_client.call_tool(
            "get_order_buy_uuid",
            {"order_uuid": state.resource_uuid}
        ))[0]

        shaped = shape_prescription(order)
        if shaped["drug"] is None:
            return {"skip_reason":"drug order has no drug or concept; nothing to explain"}
        
        return {"shaped":shaped}
    

def classify_lab(state:ReportState)-> dict:
    classification = classify_value(
        state.shaped.get("value"),
        state.shaped.get("reference_range"),
    )
    return {
        "classification":classification,
        "is_critical":classification == "critical",
    }

def route_after_fetch(state:ReportState)-> dict:
    if state.skip_reason:
        return "end"
    if state.resource_type == "lab":
        return "classify_lab"
    return "explain"
    

def _build_user_message(state: ReportState) -> str:

      if state.resource_type == "lab":
          header = "Explain this LAB RESULT to the patient."
          status_line = f"Computed status: {state.classification}\n"
      else:
          header = "Explain this PRESCRIPTION to the patient."
          status_line = ""
      return (
          f"{header}\n{status_line}"
          f"Record data (JSON):\n{json.dumps(state.shaped, indent=2, default=str)}"
      )


async def explain(state: ReportState) -> dict:

      raw = await llm.complex(
          messages=[{"role": "user", "content": _build_user_message(state)}],
          system=EXPLAIN_SYSTEM_PROMPT,
      )
      message, meta = _split_response(raw)


      is_critical = state.is_critical or meta.get("status") == "critical"

      return {
          "explanation":        message,
          "profile_extraction": meta.get("profile_extraction", {}),
          "confidence":         meta.get("explanation_confidence"),
          "is_critical":        is_critical,
      }


def _response_type(state: ReportState) -> str:
      return "lab_result" if state.resource_type == "lab" else "prescription"


def _metadata(state: ReportState) -> dict:

      return {
          "resource_type": state.resource_type,
          "resource_uuid": state.resource_uuid,
          "status":        state.classification,
          "is_critical":   state.is_critical,
          "confidence":    state.confidence,
          "test":          state.shaped.get("test"),
          "drug":          state.shaped.get("drug"),
      }


def finalize(state: ReportState) -> dict:

      CRITICAL_BANNER = (
          "⚠ This value is critically outside the normal range. Contact your "
          "healthcare provider or seek emergency care immediately."
      )


      if state.confidence == "low" or not state.explanation:
          kind = "lab result" if state.resource_type == "lab" else "prescription"
          content = (
              f"I've received a new {kind} on your record, but I'm not able to "
              "explain it reliably. Please discuss it with your doctor.\n\n"
              f"{DISCLAIMER}"
          )
          return {"response": {
              "type":     _response_type(state),
              "content":  content,
              "metadata": _metadata(state),
          }}

      content = state.explanation


      if state.is_critical and "⚠" not in content:
          content = f"{CRITICAL_BANNER}\n\n{content}"


      if "informational purposes only" not in content.lower():
          content = f"{content}\n\n{DISCLAIMER}"

      return {"response": {
          "type":     _response_type(state),
          "content":  content,
          "metadata": _metadata(state),
      }}

def build_report_subgraph()-> CompiledStateGraph:
    graph = StateGraph(ReportState)

    graph.add_node("fetch_resource", fetch_resource)
    graph.add_node("classify_lab",classify_lab)
    graph.add_node("explain",explain)
    graph.add_node("finalize",finalize)

    graph.add_edge(START, "fetch_resource")
    graph.add_conditional_edges(
        "fetch_resource",
        route_after_fetch,
        {"classify_lab":"classify_lab","explain":"explain","end":END},

    )
    graph.add_edge("classify_lab","explain")
    graph.add_edge("explain","finalize")
    graph.add_edge("finalize",END)

    return graph.compile()