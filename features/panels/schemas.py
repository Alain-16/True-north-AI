from datetime import datetime
from pydantic import BaseModel


# ── Appointments panel ────────────────────────────────────────────────
class AppointmentItem(BaseModel):
    id: str
    doctor_name: str | None = None
    specialty: str | None = None
    scheduled_at: datetime
    status: str | None = None
    source: str | None = None
    is_upcoming: bool


class AppointmentsResponse(BaseModel):
    items: list[AppointmentItem]


# ── Reports panel ─────────────────────────────────────────────────────
class ReportItem(BaseModel):
    id: str
    resource_type: str
    delivery_status: str | None = None
    ai_explanation_summary: str | None = None
    delivered_at: datetime | None = None
    patient_acknowledged_at: datetime | None = None
    created_at: datetime


class ReportsResponse(BaseModel):
    items: list[ReportItem]


# ── History panel ─────────────────────────────────────────────────────
# `context` is the shaped clinical profile from reports.service.to_history_context.
class HistoryResponse(BaseModel):
    available: bool
    last_source: str | None = None
    updated_at: datetime | None = None
    context: dict | None = None


# ── Queue panel ───────────────────────────────────────────────────────
# Live queue is not yet wired (the agent's queue flow is a stub). Surface an
# honest "unavailable" shape so the panel can render a coming-soon state.
class QueueResponse(BaseModel):
    available: bool
    position: int | None = None
    estimated_wait_minutes: int | None = None
    message: str
