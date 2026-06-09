import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db import AppointmentRecord, ReportDeliveryLog, MedicalProfile
from features.reports.service import to_history_context


async def list_appointments(session: AsyncSession, patient_id: str) -> list[dict]:
    """All of a patient's appointment records, soonest/most-recent first."""
    pid = uuid.UUID(patient_id)
    now = datetime.now(timezone.utc)

    rows = (await session.execute(
        select(AppointmentRecord)
        .where(AppointmentRecord.patient_id == pid)
        .order_by(AppointmentRecord.scheduled_at.desc())
    )).scalars().all()

    return [
        {
            "id":           str(r.id),
            "doctor_name":  r.doctor_name,
            "specialty":    r.specialty,
            "scheduled_at": r.scheduled_at,
            "status":       r.status,
            "source":       r.source,
            "is_upcoming":  r.scheduled_at >= now and r.status == "scheduled",
        }
        for r in rows
    ]


async def list_reports(session: AsyncSession, patient_id: str) -> list[dict]:
    """Reports that have been explained/delivered to the patient, newest first."""
    pid = uuid.UUID(patient_id)

    rows = (await session.execute(
        select(ReportDeliveryLog)
        .where(ReportDeliveryLog.patient_id == pid)
        .order_by(ReportDeliveryLog.created_at.desc())
    )).scalars().all()

    return [
        {
            "id":                      str(r.id),
            "resource_type":           r.resource_type,
            "delivery_status":         r.delivery_status,
            "ai_explanation_summary":  r.ai_explanation_summary,
            "delivered_at":            r.delivered_at,
            "patient_acknowledged_at": r.patient_acknowledged_at,
            "created_at":              r.created_at,
        }
        for r in rows
    ]


async def get_history(session: AsyncSession, patient_id: str) -> dict:
    """The patient's AI-extracted medical profile, shaped as clinical context."""
    pid = uuid.UUID(patient_id)

    row = (await session.execute(
        select(MedicalProfile).where(MedicalProfile.patient_id == pid)
    )).scalar_one_or_none()

    if row is None or not row.profile:
        return {"available": False, "last_source": None, "updated_at": None, "context": None}

    updated_at = row.updated_at
    context = to_history_context(
        row.profile,
        extraction_date=updated_at.isoformat() if updated_at else None,
        demographics=None,  # age/sex live in OpenMRS, not surfaced to this panel
    )
    return {
        "available":   True,
        "last_source": row.last_source,
        "updated_at":  updated_at,
        "context":     context,
    }
