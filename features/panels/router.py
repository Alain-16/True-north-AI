from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from features.auth.deps import get_current_patient
from features.panels import service
from features.panels.schemas import (
    AppointmentsResponse,
    ReportsResponse,
    HistoryResponse,
    QueueResponse,
)

router = APIRouter(prefix="/panels", tags=["panels"])


@router.get("/appointments", response_model=AppointmentsResponse)
async def appointments(patient: dict = Depends(get_current_patient),
                       session: AsyncSession = Depends(get_db)):
    items = await service.list_appointments(session, patient["patient_id"])
    return {"items": items}


@router.get("/reports", response_model=ReportsResponse)
async def reports(patient: dict = Depends(get_current_patient),
                  session: AsyncSession = Depends(get_db)):
    items = await service.list_reports(session, patient["patient_id"])
    return {"items": items}


@router.get("/history", response_model=HistoryResponse)
async def history(patient: dict = Depends(get_current_patient),
                  session: AsyncSession = Depends(get_db)):
    return await service.get_history(session, patient["patient_id"])


@router.get("/queue", response_model=QueueResponse)
async def queue(patient: dict = Depends(get_current_patient)):
    # Live queue position isn't wired yet (the agent's queue flow is a stub).
    # Return an honest "unavailable" shape so the panel renders a coming-soon state.
    return {
        "available": False,
        "position": None,
        "estimated_wait_minutes": None,
        "message": "Live queue status isn't available yet.",
    }
