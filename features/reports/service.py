import logging
from datetime import datetime, timezone
from sqlalchemy import select
from core.database import AsyncSessionLocal
from models.db import MedicalProfile
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from models.db import ReportDeliveryLog
from datetime import datetime,timedelta, timezone
from models.db import ReminderSchedule


logger = logging.getLogger(__name__)

RISK_KEYS = [
      "immunosuppressed_indicators",
      "anticoagulant_use",
      "recent_surgery",
      "pregnancy_indicators",
  ]

REFILL_LEAD_DAYS = 3


def _merge_by_key(existing: list, new: list, key: str) -> list:
  
      merged: dict = {}
      for item in [*existing, *new]:
          k = (item.get(key) or "").strip().lower()
          if not k:                       # skip entries with no usable key
              continue
          merged[k] = item
      return list(merged.values())


def _merge_strings(existing: list, new: list) -> list:
      """Case-insensitive set union, preserving the first-seen casing."""
      seen: dict = {}
      for s in [*existing, *new]:
          if not s:
              continue
          k = s.strip().lower()
          if k and k not in seen:
              seen[k] = s.strip()
      return list(seen.values())


def _merge_labs(existing: list, new: list) -> list:
 
      merged: dict = {}
      for lab in [*existing, *new]:
          test = (lab.get("test") or "").strip().lower()
          if not test:
              continue
          date = (lab.get("date") or "").strip()
          merged[(test, date)] = lab
      return list(merged.values())


def _merge_flags(existing: dict, new: dict) -> dict:
      
      return {k: bool(existing.get(k)) or bool(new.get(k)) for k in RISK_KEYS}


def merge_profile(existing: dict, new: dict) -> dict:
     
      existing = existing or {}
      new = new or {}
      return {
          "medications_identified": _merge_by_key(
              existing.get("medications_identified") or [],
              new.get("medications_identified") or [],
              "name",
          ),
          "conditions_identified": _merge_by_key(
              existing.get("conditions_identified") or [],
              new.get("conditions_identified") or [],
              "name",
          ),
          "allergies_identified": _merge_strings(
              existing.get("allergies_identified") or [],
              new.get("allergies_identified") or [],
          ),
          "lab_results": _merge_labs(
              existing.get("lab_results") or [],
              new.get("lab_results") or [],
          ),
          "risk_flags_detected": _merge_flags(
              existing.get("risk_flags_detected") or {},
              new.get("risk_flags_detected") or {},
          ),
      }
async def upsert_medical_profile(patient_id, extraction: dict, source: str | None = None) -> None:

      if not extraction:
          return  # nothing was extracted — don't bump version for an empty merge

      try:
          async with AsyncSessionLocal() as session:
              row = (await session.execute(
                  select(MedicalProfile).where(MedicalProfile.patient_id == patient_id)
              )).scalar_one_or_none()

              if row is None:
                  session.add(MedicalProfile(
                      patient_id=patient_id,
                      profile=merge_profile({}, extraction),
                      last_source=source,
                      version=1,
                  ))
              else:
                  # Reassign (not mutate) so SQLAlchemy marks the JSONB column dirty.
                  # Stored first, incoming second — the order _merge_by_key relies on.
                  row.profile = merge_profile(row.profile, extraction)
                  row.version = row.version + 1
                  row.last_source = source
                  row.updated_at = datetime.now(timezone.utc)   # no onupdate; set it ourselves

              await session.commit()
      except Exception:
          logger.exception("Failed to upsert medical profile for patient_id=%s", patient_id)


def _age_risk(age) -> str:
      if isinstance(age, int) and not isinstance(age, bool):
          if age < 2:
              return "pediatric_under_2"
          if age > 65:
              return "elderly_over_65"
      return "none"


def to_history_context(
      profile: dict,
      *,
      extraction_date: str | None = None,
      demographics: dict | None = None,
  ) -> dict:

      profile = profile or {}
      flags = profile.get("risk_flags_detected") or {}
      demo = demographics or {}

      active_medications = [
          {"name": m.get("name"), "dosage": m.get("dosage"),
           "source_document": "report_explanation_feature"}
          for m in (profile.get("medications_identified") or [])
      ]
      conditions = [
          {"name": c.get("name"),
           # §24 uses "mentioned"; §22's vocabulary is active|resolved|unknown
           "status": "unknown" if c.get("status") == "mentioned" else (c.get("status") or "unknown"),
           "source_document": "report_explanation_feature"}
          for c in (profile.get("conditions_identified") or [])
      ]
      recent_lab_results = [
          {"test": l.get("test"), "value": l.get("value"),
           "date": l.get("date"), "flag": l.get("flag")}
          for l in (profile.get("lab_results") or [])
      ]

      pregnancy = demo.get("pregnancy_status")
      if pregnancy is None and flags.get("pregnancy_indicators"):
          pregnancy = "possible (from report extraction)"

      return {
          "source": "report_explanation_feature",
          "extraction_date": extraction_date,
          "confidence_note": (
              "This data was extracted by AI from clinical records. It may be "
              "incomplete or outdated. Verify critical details with the patient."
          ),
          "demographics": {
              "age": demo.get("age"),
              "sex": demo.get("sex"),
              "pregnancy_status": pregnancy,
          },
          "active_medications": active_medications,
          "allergies": profile.get("allergies_identified") or [],
          "conditions": conditions,
          "surgical_history": [],   # current report prompt doesn't extract procedures
          "recent_lab_results": recent_lab_results,
          "risk_flags": {
              "immunosuppressed":   bool(flags.get("immunosuppressed_indicators")),
              "anticoagulant_use":  bool(flags.get("anticoagulant_use")),
              "recent_surgery_30d": bool(flags.get("recent_surgery")),
              "age_risk":           _age_risk(demo.get("age")),
          },
      }


async def claim_delivery(patient_id,resource_id: str, resource_type:str,channel:str)-> bool:
     async with AsyncSessionLocal() as session:
          stmt = (
               pg_insert(ReportDeliveryLog).values(
                    patient_id = patient_id,
                    openmrs_resource_id = resource_id,
                    resource_type = resource_type,
                    channel = channel,
                    delivery_status = "pending",
               )
               .on_conflict_do_nothing(constraint="uq_report_patient_resource")
               .returning(ReportDeliveryLog.id)

          )
          claimed = (await session.execute(stmt)).scalar_one_or_none()
          await session.commit()
          return claimed is not None
     


async def mark_delivery(
      patient_id,
      resource_id: str,
      status: str,
      summary: str | None = None,
  ) -> None:
  
      values: dict = {"delivery_status": status}
      if summary is not None:
          values["ai_explanation_summary"] = summary
      if status == "sent":
          values["delivered_at"] = datetime.now(timezone.utc)

      try:
          async with AsyncSessionLocal() as session:
              await session.execute(
                  update(ReportDeliveryLog)
                  .where(
                      ReportDeliveryLog.patient_id == patient_id,
                      ReportDeliveryLog.openmrs_resource_id == resource_id,
                  )
                  .values(**values)
              )
              await session.commit()
      except Exception:
          logger.exception(
              
              status, patient_id, resource_id,
          )


def _parse_omrs_dt(s:str | None) -> datetime | None:
     if not s:
          return None
     try:
          return datetime.fromisoformat(s.replace("Z", "+00:00"))
     except ValueError:
        return None
     

    
def build_followups(
          resource_type: str,
          shaped: dict,
          classification:str | None,
          is_critical: bool,
          channel: str,
          now: datetime | None = None,
) -> list[dict]:
     
     now = now or datetime.now(timezone.utc)
     shaped = shaped or {}
     rows : list[dict]=[]

     if resource_type == "prescription":
          expire = _parse_omrs_dt(shaped.get("auto_expire_date"))
          if expire is None:
               activated = _parse_omrs_dt(shaped.get("date_activated"))
               duration = shaped.get("duration")
               units = (shaped.get("duration_units") or "").lower()
               if activated and isinstance(duration,(int,float)) and "day" in units:
                    expire = activated + timedelta(days=duration)
                
          if expire is not None:
                    trigger = expire - timedelta(days=REFILL_LEAD_DAYS)
                    if trigger > now:
                         rows.append({
                              "event_type":"medication_refill",
                              "trigger_at":trigger,
                              "channel":channel
                         })
     else:
                    if is_critical:
                         rows.append({
                              "event_type":"lab_followup_urgent",
                              "trigger_at":now + timedelta(days=1),
                              "channel":channel
                         })

                    elif classification == "abnormal":
                         rows.append({
                              "event_type":"lab_followup",
                              "trigger_at":now + timedelta(days=3),
                              "channel":channel
                         })
     return rows

async def plan_followups(
      patient_id,
      resource_type: str,
      shaped: dict,
      classification: str | None,
      is_critical: bool,
      channel: str,
  ) -> None:

      rows = build_followups(resource_type, shaped or {}, classification, is_critical, channel)
      if not rows:
          return  # e.g. a normal lab — nothing to follow up

      try:
          async with AsyncSessionLocal() as session:
              await session.execute(
                  pg_insert(ReminderSchedule),
                  [
                      {
                          "patient_id":     patient_id,
                          "appointment_id": None,           # report-driven, not appointment-driven
                          "event_type":     r["event_type"],
                          "trigger_at":     r["trigger_at"],
                          "channel":        r["channel"],
                          "template_name":  None,           # web; WhatsApp templates deferred
                      }
                      for r in rows
                  ],
              )
              await session.commit()
      except Exception:
          logger.exception("Failed to schedule follow-ups for patient_id=%s", patient_id)
