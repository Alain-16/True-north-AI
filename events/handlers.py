import json
import logging
from sqlalchemy import select
from core.database import AsyncSessionLocal
from models.db import Patient
from agent.subgraphs.reports import build_report_subgraph
from features.reports.service import (claim_delivery,mark_delivery,upsert_medical_profile,plan_followups)
from agent.mcp_client import mcp_client

logger = logging.getLogger(__name__)

report_graph = build_report_subgraph()


TOPIC_RESOURCE_TYPE = {
      "/topic/CREATED:org.openmrs.Obs":       "lab",
      "/topic/CREATED:org.openmrs.DrugOrder": "prescription",
  }

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

      