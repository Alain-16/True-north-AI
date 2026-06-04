from sqlalchemy import select

from core.database import AsyncSessionLocal
from models.db import AppointmentRecord
import logging
from datetime import datetime, timezone
from sqlalchemy import update
from models.db import ReminderSchedule
# import httpx
# from core.config import get_settings
# from models.db import Patient
  


# WHATSAPP_API_VERSION = "v21.0"



logger = logging.getLogger(__name__)

REMINDER_TEMPLATES = {
       "appointment_reminder": "appointment_reminder",
       "medication_refill":    "medication_refill_reminder",
       "lab_followup":         "lab_result_available",
       "lab_followup_urgent":  "lab_result_available",
   }


async def _get_appointment(appointment_id) -> AppointmentRecord | None:

      if appointment_id is None:
          return None
      async with AsyncSessionLocal() as session:
          return (await session.execute(
              select(AppointmentRecord).where(AppointmentRecord.id == appointment_id)
          )).scalar_one_or_none()


def render_reminder(event_type: str, appt: AppointmentRecord | None) -> str:

      if event_type == "appointment_reminder":
          if appt is None:
              # Appointment row gone (cancelled/deleted) but reminder still pending.
              return "Reminder: you have an upcoming appointment at the hospital."
          when = appt.scheduled_at.strftime("%a %d %b at %H:%M")
          specialty = appt.specialty or "your appointment"
          doctor = f" with {appt.doctor_name}" if appt.doctor_name else ""
          return f"Reminder: you have a {specialty} appointment{doctor} on {when}."

      if event_type == "medication_refill":
          return ("Reminder: one of your prescriptions may be running low soon — "
                  "consider arranging a refill with the hospital.")

      if event_type == "lab_followup_urgent":
          return ("Reminder: please contact your doctor soon about your recent "
                  "lab result.")

      if event_type == "lab_followup":
          return ("Reminder: please follow up with your doctor about your recent "
                  "lab result when convenient.")

      # Unknown event_type — never crash the scan over one odd row.
      return "Reminder: you have a notification from the hospital."

async def claim_due_reminders() -> list:
      """Atomically claim all due, pending reminders."""

      now = datetime.now(timezone.utc)
      async with AsyncSessionLocal() as session:
          rows = (await session.execute(
              update(ReminderSchedule)
              .where(
                  ReminderSchedule.status == "pending",
                  ReminderSchedule.trigger_at <= now,
              )
              .values(status="sending")
              .returning(
                  ReminderSchedule.id,
                  ReminderSchedule.patient_id,
                  ReminderSchedule.appointment_id,
                  ReminderSchedule.event_type,
                  ReminderSchedule.channel,
              )
          )).all()
          await session.commit()
      return rows

async def mark_reminder(reminder_id, status: str, delivery_status: str | None = None) -> None:
      """Advance a claimed reminder to sent | failed. Stamps sent_at on 'sent'."""
      values: dict = {"status": status}
      if status == "sent":
          values["sent_at"] = datetime.now(timezone.utc)
      if delivery_status is not None:
          values["delivery_status"] = delivery_status

      async with AsyncSessionLocal() as session:
          await session.execute(
              update(ReminderSchedule)
              .where(ReminderSchedule.id == reminder_id)
              .values(**values)
          )
          await session.commit()


async def scan_and_send() -> None:
      """One scan pass: claim due reminders, render + deliver each, mark sent/failed.
"""
      try:
          rows = await claim_due_reminders()
      except Exception:
          logger.exception("Reminder scan: failed to claim due rows")
          return

      if not rows:
          return
      logger.info("Reminder scan: processing %d due reminder(s)", len(rows))

      for row in rows:
          try:
              appt = await _get_appointment(row.appointment_id)
              message = render_reminder(row.event_type, appt)

              # --- WhatsApp delivery (DEFERRED — commented; see Block 3) ----------
              # if row.channel == "whatsapp":
              #     phone = await _patient_phone(row.patient_id)
              #     if phone:
              #         await _deliver_whatsapp_template(phone, message)
              # -------------------------------------------------------------------

              logger.info("Reminder %s (%s) → %s", row.id, row.event_type, message)
              await mark_reminder(row.id, "sent", delivery_status="delivered")
          except Exception:
              logger.exception("Reminder %s failed", row.id)
              await mark_reminder(row.id, "failed", delivery_status="error")


  # async def _patient_phone(patient_id) -> str | None:
  #     async with AsyncSessionLocal() as session:
  #         return (await session.execute(
  #             select(Patient.whatsapp_phone).where(Patient.id == patient_id)
  #         )).scalar_one_or_none()
  #
  # async def _deliver_whatsapp_template(phone: str, event_type: str, message: str) -> None:
  #     settings = get_settings()
  #     url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{settings.whatsapp_phone_number_id}/messages"
  #     headers = {"Authorization": f"Bearer {settings.meta_whatsapp_token}",
  #                "Content-Type": "application/json"}
  #     template = REMINDER_TEMPLATES.get(event_type, "appointment_reminder")
  #     payload = {
  #         "messaging_product": "whatsapp",
  #         "to": phone,
  #         "type": "template",
  #         "template": {
  #             "name": template,
  #             "language": {"code": "en"},
  #             "components": [{"type": "body",
  #                             "parameters": [{"type": "text", "text": message}]}],
  #         },
  #     }
  #     async with httpx.AsyncClient(timeout=15.0) as http:
  #         resp = await http.post(url, json=payload, headers=headers)
  #         resp.raise_for_status()
