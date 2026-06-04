import json
import logging
from sqlalchemy import select
from core.database import AsyncSessionLocal
from models.db import Patient
from agent.subgraphs.reports import build_report_subgraph
from features.reports.service import (claim_delivery,mark_delivery,upsert_medical_profile,plan_followups)
from agent.mcp_client import mcp_client
from core.config import get_settings
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func
import asyncio
# import httpx
# from core.config import get_settings

# WHATSAPP_API_VERSION = "v21.0"

logger = logging.getLogger(__name__)

report_graph = build_report_subgraph()


TOPIC_RESOURCE_TYPE = {
      "/topic/CREATED:org.openmrs.Obs":       "lab",
      "/topic/CREATED:org.openmrs.DrugOrder": "prescription",
      "/topic/CREATED:org.openmrs.Patient":   "patient",
  }
 
EVENT_HANDLERS = {
    "lab":          handle_report_event,      # noqa: F821  (defined above in handlers.py)
    "prescription": handle_report_event,      # noqa: F821
    "patient":      handle_patient_event,     # two topics legitimately share a handler
}

def normalize_phone(raw:str|None, default_cc: str)-> str |None:
    if not raw:
        return None
    
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    if digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = default_cc + digits[1:]
    elif not digits.startswith(default_cc):
        digits = default_cc + digits
    
    return digits or None


def _flatten_map_message(payload: dict) -> dict:

      entries = (payload.get("map") or {}).get("entry") or []
      if isinstance(entries, dict):
          entries = [entries]
      out = {}
      for entry in entries:
          pair = entry.get("string")
          if isinstance(pair, list) and len(pair) == 2:
              out[pair[0]] = pair[1]
      return out

def parse_event(destination: str, body: str) -> dict | None:
      resource_type = TOPIC_RESOURCE_TYPE.get(destination)
      if resource_type is None:
          return None
      try:
          payload = json.loads(body)
      except (json.JSONDecodeError, ValueError):
          logger.warning("Unparseable event body on %s: %r", destination, body)
          return None

      fields = _flatten_map_message(payload)
      resource_uuid = fields.get("uuid")
      if not resource_uuid:
          logger.warning("Event missing uuid on %s: %r", destination, fields)
          return None
      # Note: no patient in the event — the handler fetches the resource to find it.
      return {"resource_type": resource_type, "resource_uuid": resource_uuid}


async def _patient_for(resource_type: str, resource_uuid: str) -> dict | None:
      if resource_type == "prescription":
          order = (await mcp_client.call_tool("get_order_by_uuid", {"order_uuid": resource_uuid}))[0]
          patient_uuid = (order.get("patient") or {}).get("uuid")
      else:  # lab
          obs = (await mcp_client.call_tool("get_obs_by_uuid", {"obs_uuid": resource_uuid}))[0]
          patient_uuid = (obs.get("person") or {}).get("uuid")

      if not patient_uuid:
          return None
      return (await mcp_client.call_tool("get_patient_by_uuid", {"patient_uuid": patient_uuid}))[0]



async def handle_report_event(event: dict) -> None:
      resource_type = event["resource_type"]
      resource_uuid = event["resource_uuid"]

      patient = await _patient_for(resource_type, resource_uuid)
      identifier = (patient or {}).get("identifier")
      if not identifier:
          logger.info("No patient resolved for %s %s; skipping", resource_type, resource_uuid)
          return

      resolved = await _resolve_patient(identifier)
      if resolved is None:
          logger.info("No local patient for %s; skipping %s %s", identifier, resource_type, resource_uuid)
          return
      patient_id, channel = resolved

      if not await claim_delivery(patient_id, resource_uuid, resource_type, channel):
          logger.info("Duplicate event for %s %s; skipping", resource_type, resource_uuid)
          return

      try:
          state = await report_graph.ainvoke({
              "resource_uuid":      resource_uuid,
              "resource_type":      resource_type,
              "openmrs_patient_id": identifier,
              "patient_id":         str(patient_id),
              "channel":            channel,
          })
      except Exception:
          logger.exception("ReportSubgraph failed for %s %s", resource_type, resource_uuid)
          await mark_delivery(patient_id, resource_uuid, "failed")
          return

      if state.get("skip_reason"):
          await mark_delivery(patient_id, resource_uuid, "skipped")
          return

      await upsert_medical_profile(patient_id, state.get("profile_extraction") or {},
                                   source=f"{resource_type}:{resource_uuid}")
      response = state.get("response") or {}
      await mark_delivery(patient_id, resource_uuid, "sent", summary=response.get("content"))

      #    phone = await _patient_phone(patient_id)
      #     if phone:
      #         # We don't track last-inbound timestamps yet, so assume the 24h
      #         # window is CLOSED for a proactive push → template. Flip to
      #         # window_open=True once inbound timestamps are tracked.
      #         await _deliver_whatsapp(phone, response.get("content", ""), window_open=False)
        

      # Plan follow-ups from the result (refill nudge / lab follow-up). 
      await plan_followups(
          patient_id, resource_type,
          state.get("shaped") or {},
          state.get("classification"),
          bool(state.get("is_critical")),
          channel,
      )
      logger.info("Delivered %s %s to patient %s", resource_type, resource_uuid, patient_id)
      
      


async def _resolve_patient(openmrs_patient_id: str):
      async with AsyncSessionLocal() as session: 
          row = (await session.execute(
              select(Patient.id, Patient.preferred_channel)
              .where(Patient.openmrs_patient_id == openmrs_patient_id)
          )).first()
      if row is None:
          return None
      local_id, channel = row
      return local_id, (channel or "web")

  # async def _patient_phone(patient_id) -> str | None:
  #     async with AsyncSessionLocal() as session:
  #         return (await session.execute(
  #             select(Patient.whatsapp_phone).where(Patient.id == patient_id)
  #         )).scalar_one_or_none()
  #
  # async def _deliver_whatsapp(to_phone: str, explanation: str, *, window_open: bool) -> None:
  #     """Proactive WhatsApp delivery via Meta Cloud API.
  #
  #     WhatsApp's 24h customer-service window: free-form text is only allowed within
  #     24h of the patient's last INBOUND message; outside it, a pre-approved template
  #     is required. A proactive report push is normally outside the window.
  #     """
  #     settings = get_settings()
  #     url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{settings.whatsapp_phone_number_id}/messages"
  #     headers = {
  #         "Authorization": f"Bearer {settings.meta_whatsapp_token}",
  #         "Content-Type": "application/json",
  #     }
  #
  #     if window_open:
  #         # Inside the 24h window → free-form text is allowed.
  #         payload = {
  #             "messaging_product": "whatsapp",
  #             "to": to_phone,
  #             "type": "text",
  #             "text": {"body": explanation[:4096]},        # WhatsApp text body limit
  #         }
  #     else:
  #         # Outside the window → pre-approved template + deep link to /chat.
  #         payload = {
  #             "messaging_product": "whatsapp",
  #             "to": to_phone,
  #             "type": "template",
  #             "template": {
  #                 "name": "lab_result_available",          # one of the 4 approved templates
  #                 "language": {"code": "en"},
  #                 "components": [{
  #                     "type": "body",
  #                     "parameters": [{"type": "text", "text": "your results"}],
  #                 }],
  #             },
  #         }
  #
  #     async with httpx.AsyncClient(timeout=15.0) as http:
  #         resp = await http.post(url, json=payload, headers=headers)
  #         resp.raise_for_status()


async def handle_patient_event(event: dict)-> None:
    
        resource_uuid = event["resource_uuid"]
        patient = (await mcp_client.call_tool(
            "get_patient_by_uuid",{"patient_uuid": resource_uuid}
        ))[0]

        identifier = patient.get("identifier")

        if not identifier:
            logger.info("Patient event %s has no identifier; skipping", resource_uuid)
            return
        
        settings = get_settings()
        email = patient.get("email")
        phone = normalize_phone(patient.get("phone"), settings.default_country_code)

        async with AsyncSessionLocal() as session:
            try:
                await _upsert_patient(session,identifier,email,phone)
                await session.commit()
            except IntegrityError:
                await session.rollback()
                logger.exception("could not upsert patient openmrs_id= %s",identifier)
                return
        logger.info("Synced patient %s (openmrs_id=%s)",resource_uuid,identifier)

    


async def _upsert_patient(session,identifier:str,email:str | None, phone:str | None) -> None:

    stmt = pg_insert(Patient).values(
        openmrs_patient_id = identifier,
        web_email = email,
        whatsapp_phone = phone,
        status = "pending_channel_link",
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=["openmrs_patient_id"],
        set_= {
            "web_email": func.coalesce(stmt.excluded.web_email,Patient.web_email),
            "whatsapp_phone": func.coalesce(
                stmt.excluded.whatsapp_phone, Patient.whatsapp_phone
            ),
            "updated_at": func.now(),
        },
    )
    await session.execute(stmt)


