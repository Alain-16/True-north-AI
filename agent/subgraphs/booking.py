from langgraph.graph import StateGraph,START,END
from langgraph.graph.state import CompiledStateGraph
from agent.state import AgentState
import json
from langchain_core.messages import HumanMessage
from agent.llm_client import llm
from agent.mcp_client import mcp_client
from datetime import datetime,timedelta,timezone
import logging
from sqlalchemy import select
from core.database import AsyncSessionLocal
from sqlalchemy.dialects.postgresql import insert as pg_insert
from models.db import Patient,AppointmentRecord,ReminderSchedule

logger = logging.getLogger(__name__)

REMINDER_OFFSETS =[
     ("appointment_reminder_7d", timedelta(days=7)),
     ("appointment_reminder_1d", timedelta(days=1)),
     ("appointment_reminder_2h", timedelta(hours=2)),

]

TIME_OF_DAY_WINDOWS = {
      "morning":   (6, 12),
      "afternoon": (12, 17),
      "evening":   (17, 21),
  }


MATCH_SPECIALITY_PROMPT = """
  You match a patient's requested specialty to one of a hospital's available specialities.

  You are given the patient's phrasing and a list of available speciality names.
  Return the EXACT name of the best-matching speciality — copied verbatim from the list.
  If nothing is a reasonable match, return exactly: none

  Return only the name (or "none"). No explanation, no punctuation, no quotes.

"""

EXTRACT_SYSTEM_PROMPT="""

  You extract appointment-booking details from a patient's message.

  Today is {today}. Resolve any date hints the patient mentions to a concrete
  ISO date (YYYY-MM-DD).
  - "wednesday" or "this wednesday" → the next Wednesday on or after today
  - "next monday" → the Monday of the following week (skip the current week)
  - "tomorrow" → today + 1 day
  - "today" → today
  - "as soon as possible" or no date mentioned → null

  For time-of-day, bucket into one of: morning | afternoon | evening.
  - "morning" / "9 am" / "before lunch" → morning
  - "afternoon" / "after lunch" / "2 pm" → afternoon
  - "evening" / "after 5" → evening
  - no time mentioned → null

  Return valid JSON only — no explanation, no markdown, no code fences:
  {{"specialty": <string or null>, "date": <YYYY-MM-DD or null>, "time_of_day": <"morning"|"afternoon"|"evening" or null>}}
"""

SELECTION_PROMPT = """
  A patient was shown a numbered list of appointment times and has replied.

  Decide what they want. Return valid JSON only — no markdown, no code fences:
  {"action": "select" | "cancel" | "unclear", "index": <number or null>}

  select  — they chose an option; "index" is the option number they picked.
  cancel  — they want to abandon booking (e.g. "never mind", "cancel", "stop").
  unclear — the reply neither picks an option nor asks to cancel.
  """

async def extract_params(state: AgentState) -> dict:
      user_message = [m for m in state.messages if isinstance(m, HumanMessage)]
      latest = user_message[-1].content if user_message else ""

     
      today_iso = datetime.now(timezone.utc).date().isoformat()

      raw = await llm.simple(
          prompt=f"Patient message:{latest}",
          system=EXTRACT_SYSTEM_PROMPT.format(today=today_iso),
      )
      print("debug latest:", repr(latest))
      print("debug:", repr(raw))
      try:
          parsed = json.loads(raw)
      except (json.JSONDecodeError, ValueError):
          parsed = {}

      return {
          "flow_state": {
              **state.flow_state,
              "specialty":   parsed.get("specialty"),
              "date":        parsed.get("date"),         
              "time_of_day": parsed.get("time_of_day"),  
          }
      }


async def resolve_service(state: AgentState) -> dict:
      specialty = state.flow_state.get("specialty")
      if not specialty:
            return {
                  "response":{
                        "type":"text",
                        "content":"which speciality or service are you looking for ? (e.g General medicine)",
                  }
            }
      specialties = await mcp_client.call_tool("list_specialities",{})
      print("DEBUG specialties:", [(s["uuid"], s["name"]) for s in specialties])
      matched = await _match_speciality(specialty,specialties)
      print("DEBUG matched:", matched)
      if matched is None:
            names = ", ".join(s["name"] for s in specialties)
            return {
                  "response":{
                        "type":"text",
                        "content":f"I couldn't match '{specialty}' to a service available:{names}",
                  }
            }
      services = await mcp_client.call_tool(
            "search_services",{"speciality_uuid":matched["uuid"]}
      )
      print("DEBUG services:", services) 
      if not services:
            return {
                  "response":{
                        "type":"text",
                        "content":f"There are no bookable services under {matched['name']} right now.",
                  }
            }
      service = services[0]
      return {
            "flow_state":{
                  **state.flow_state,
                  "service":service,
                  "service_uuid":service["uuid"],
            }
      }


async def generate_slots(state: AgentState) -> dict:
      service        = state.flow_state["service"]
      service_uuid   = state.flow_state["service_uuid"]
      requested_date = state.flow_state.get("date")
      time_of_day    = state.flow_state.get("time_of_day")
      duration       = timedelta(minutes=service.get("durationMins") or 30)

      today = datetime.now(timezone.utc).date()

      # Build the days to try. Requested day goes FIRST so we honor it when possible;
      # then we tack on the next 14 days as fallback so we always have something to
      # offer, even if the requested day is closed or full.
      days_to_try: list = []
      if requested_date:
          try:
              target = datetime.strptime(requested_date, "%Y-%m-%d").date()
              if target >= today:
                  days_to_try.append(target)
          except ValueError:
              # Malformed date from the LLM — ignore preference, fall through to default scan.
              pass
      days_to_try += [
          today + timedelta(days=i)
          for i in range(1, 15)
          if (today + timedelta(days=i)) not in days_to_try
      ]

      candidates: list[dict] = []
      fallback_used = False

      for idx, day in enumerate(days_to_try):
          window = _day_window(service, day)
          if window is None:
              continue
          start_dt, end_dt, cap = window


          if time_of_day and time_of_day in TIME_OF_DAY_WINDOWS:
              tod_start_h, tod_end_h = TIME_OF_DAY_WINDOWS[time_of_day]
              tod_start = start_dt.replace(hour=tod_start_h, minute=0, second=0, microsecond=0)
              tod_end   = start_dt.replace(hour=tod_end_h,   minute=0, second=0, microsecond=0)
              start_dt  = max(start_dt, tod_start)
              end_dt    = min(end_dt,   tod_end)
              if start_dt >= end_dt:
                  continue

          load = (await mcp_client.call_tool("get_service_load", {
              "service_uuid":   service_uuid,
              "start_datetime": start_dt.isoformat(),
              "end_datetime":   end_dt.isoformat(),
          }))[0]
          if cap is not None and load >= cap:
              continue

          slot_start = start_dt
          while slot_start + duration <= end_dt:
              candidates.append({
                  "start": slot_start.isoformat(),
                  "end":   (slot_start + duration).isoformat(),
                  "label": slot_start.strftime("%a %d %b, %H:%M"),
              })
              slot_start += duration

          if candidates:
              candidates = candidates[:5]

              if requested_date and idx > 0:
                  fallback_used = True
              break

      if not candidates:
          if requested_date or time_of_day:
              msg = (f"I couldn't find any {time_of_day or 'available'} openings "
                     f"on {requested_date or 'the days you asked about'} "
                     "or in the next two weeks. ")
          else:
              msg = "I couldn't find any openings in the next two weeks. "
          return {"response": {
              "type": "text",
              "content": msg + "Please try a different service or contact the hospital.",
          }}

      return {
          "flow_state": {
              **state.flow_state,
              "candidates":    candidates,
              "fallback_used": fallback_used,
          },
      }



async def present_slots(state: AgentState) -> dict:
      candidates    = state.flow_state["candidates"]
      fallback_used = state.flow_state.get("fallback_used")
      requested_date = state.flow_state.get("date")

      options = "\n".join(f"{i}. {c['label']}" for i, c in enumerate(candidates, 1))

      if fallback_used and requested_date:
          preamble = f"{requested_date} isn't available — here are the next openings instead:"
      else:
          preamble = "Here are the next available appointment times:"

      content = f"{preamble}\n\n{options}\n\nReply with a number to book."
      return {
          "flow_state": {**state.flow_state, "step": "awaiting_selection"},
          "response":   {"type": "text", "content": content},
      }




async def handle_selection(state: AgentState) -> dict:
      user_messages = [m for m in state.messages if isinstance(m, HumanMessage)]
      latest = user_messages[-1].content if user_messages else ""
      candidates = state.flow_state.get("candidates", [])

      action, index = await _parse_selection(latest, candidates)

      if action == "cancel":
          return {"flow_state": {}, "response": {
              "type": "text",
              "content": "No problem — I've cancelled that booking request.",
          }}

      if action != "select":
          return {"response": {
              "type": "text",
              "content": f"Sorry, I didn't catch that — please reply with a "
                         f"number from 1 to {len(candidates)}.",
          }}

      chosen = candidates[index - 1]
      return {"flow_state": {**state.flow_state, "chosen": chosen}}



async def confirm_create(state: AgentState) -> dict:
      flow = state.flow_state
      chosen = flow["chosen"]
      service = flow["service"]


      patient = (await mcp_client.call_tool(
          "get_patient_by_identifier", {"identifier": state.openmrs_patient_id}
      ))[0]

      appt_args = {
          "patient_uuid": patient["uuid"],
          "service_uuid": flow["service_uuid"],
          "start_datetime": chosen["start"],
          "end_datetime": chosen["end"],
      }

      conflicts = (await mcp_client.call_tool("check_appointment_conflicts", appt_args))[0]
      if conflicts:
          return {"response": {
              "type": "text",
              "content": f"Sorry — you already have a booked appointment {chosen['label']}. "
                         "Please reply with another number from the list.",
          }}

      appt = (await mcp_client.call_tool("create_appointment", appt_args))[0]
      number = appt.get("appointmentNumber", "—")

      await _persist_appointment(state,appt,chosen,service)

      return {
          "flow_state": {},
          "response": {
              "type": "text",
              "content": f"Booked — {service['name']} on {chosen['label']}. "
                         f"Your appointment number is {number}.",
          },
      }

async def _persist_appointment(state:AgentState,appt:dict, chosen:dict, service:dict)-> None:
     
     try:
          async with AsyncSessionLocal() as session:
               result = await session.execute(
                    select(Patient.id).where(
                         Patient.openmrs_patient_id == state.openmrs_patient_id
                    )
               )
               local_patient_id = result.scalar_one_or_none()
               if local_patient_id is None:
                      logger.warning(
                           "No local patient row for openmrs_patient_id=%s - skipping appointment mirroring",
                           state.openmrs_patient_id
                      )
                      return
               scheduled_at = datetime.fromisoformat(chosen["start"])
               stmt = pg_insert(AppointmentRecord).values(
                    patient_id = local_patient_id,
                    openmrs_appt_id = appt["uuid"],
                    specialty = service.get("name"),
                    scheduled_at = scheduled_at,
               ).on_conflict_do_nothing(index_elements=["openmrs_appt_id"]).returning(AppointmentRecord.id)
               new_appt_id = (await session.execute(stmt)).scalar_one_or_none()
               if new_appt_id is None:
                      await session.commit()
                      return
               
               now = datetime.now(timezone.utc)
               template = "appointment_reminder" if state.channel == "whatsapp" else None
               reminder_rows =[
                    {
                         "patient_id":local_patient_id,
                         "appointment_id":new_appt_id,
                         "event_type":"appointment_reminder",
                         "trigger_at":scheduled_at - delta,
                         "channel":state.channel,
                         "template_name":template,

                    }
                    for _label, delta in REMINDER_OFFSETS
                    if scheduled_at - delta > now
               ]
               if reminder_rows:
                      await session.execute(pg_insert(ReminderSchedule),reminder_rows)
                  
               await session.commit()

               
     except Exception:
          logger.exception(
               "Failed to mirror appointment to local DB;"
               "Openmrs booking succeeded (uuid=%s, number=%s)",
               appt.get("uuid"),appt.get("appointmentNumber"),
          )


def route_entry(state:AgentState)-> str:
      step = state.flow_state.get("step")
      if step == "awaiting_selection":
            return "handle_selection"
      if state.flow_state.get("specialty"):
            return "resolve_service"
      return "extract_params"

def route_after_resolve(state:AgentState)-> str:
      return "end" if state.response else "generate_slots"

def _day_window(service: dict, day) -> tuple | None:
      """Resolve one calendar day's bookable window for a service.

      Returns (start_dt, end_dt, max_appointments) in UTC, or None if the
      service is not available that day.
      """
      weekday = day.strftime("%A").upper()  # e.g. "MONDAY"
      weekly = service.get("weeklyAvailability") or []

      if weekly:
          entry = next((w for w in weekly if w.get("dayOfWeek") == weekday), None)
          if entry is None:
              return None  # weekly schedule defined, this day not listed → closed
          start_s, end_s = entry["startTime"], entry["endTime"]
          cap = entry.get("maxAppointmentsLimit")
      elif service.get("startTime") and service.get("endTime"):
          start_s, end_s = service["startTime"], service["endTime"]
          cap = service.get("maxAppointmentsLimit")
      else:
          start_s, end_s = "09:00:00", "17:00:00"
          cap = None

      start_t = datetime.strptime(start_s, "%H:%M:%S").time()
      end_t = datetime.strptime(end_s, "%H:%M:%S").time()
      start_dt = datetime.combine(day, start_t, tzinfo=timezone.utc)
      end_dt = datetime.combine(day, end_t, tzinfo=timezone.utc)
      return start_dt, end_dt, cap

def route_after_generate(state: AgentState) -> str:
      return "end" if state.response else "present_slots"


async def _parse_selection(message: str, candidates: list) -> tuple:
      options = "\n".join(
          f"{i}. {c['label']}" for i, c in enumerate(candidates, 1)
      )
      raw = await llm.simple(
          prompt=f"Options:\n{options}\n\nPatient reply: {message}",
          system=SELECTION_PROMPT,
      )
      try:
          parsed = json.loads(raw)
      except (json.JSONDecodeError, ValueError):
          return "unclear", None

      action = parsed.get("action")
      index = parsed.get("index")
      if action == "select" and isinstance(index, int) and 1 <= index <= len(candidates):
          return "select", index
      if action == "cancel":
          return "cancel", None
      return "unclear", None

def route_after_selection(state: AgentState) -> str:
      return "end" if state.response else "confirm_create"


async def _match_speciality(specialty:str,specialties:list)-> dict | None:
      names = [s["name"] for s in specialties]
      raw = await llm.simple(
            prompt =f'patient wants: "{specialty}"\nAvailable specialities:{names}',
            system = MATCH_SPECIALITY_PROMPT,
      )
      choice = raw.strip().strip('"').lower()
      for specialty in specialties:
            if specialty["name"].lower() == choice:
                  return specialty
      return None
def build_booking_subgraph() -> CompiledStateGraph:
      graph = StateGraph(AgentState)

      graph.add_node("extract_params", extract_params)
      graph.add_node("resolve_service", resolve_service)
      graph.add_node("generate_slots", generate_slots)
      graph.add_node("present_slots", present_slots)
      graph.add_node("handle_selection", handle_selection)
      graph.add_node("confirm_create", confirm_create)

      
      graph.add_conditional_edges(
          START,
          route_entry,
          {"extract_params": "extract_params",
           "handle_selection": "handle_selection",
           "resolve_service":"resolve_service",
           },
      )

      
      graph.add_edge("extract_params", "resolve_service")
      graph.add_conditional_edges(
          "resolve_service",
          route_after_resolve,
          {"generate_slots": "generate_slots", "end": END},
      )
      graph.add_conditional_edges(
          "generate_slots",
          route_after_generate,
          {"present_slots": "present_slots", "end": END},
      )
      graph.add_edge("present_slots", END)

      
      graph.add_conditional_edges(
          "handle_selection",
          route_after_selection,
          {"confirm_create": "confirm_create", "end": END},
      )
      graph.add_edge("confirm_create", END)

      return graph.compile()
