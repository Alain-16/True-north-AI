from mcp_server.app import mcp
from mcp_server.openmrs_client import client, to_openmrs_datetime
from datetime import datetime
from typing import Literal

@mcp.tool()
async def list_specialities()-> list:
    return await client.get("speciality/all")

@mcp.tool()
async def search_services(
    speciality_uuid: str | None=None,
    name: str | None = None,
) -> list:
    services = await client.get("appointmentService/all/default")

    if speciality_uuid is not None:
        services = [
            s for s in services
            if (s.get("speciality") or {}).get("uuid") == speciality_uuid
        ]
    if name is not None:
        services = [
            s for s in services if name.lower() in s ["name"].lower()
        ]
    return services

@mcp.tool()
async def get_service_load(
    service_uuid: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> int:
    params ={
        "uuid": service_uuid,
        "startDateTime": to_openmrs_datetime(start_datetime),
        "endDateTime": to_openmrs_datetime(end_datetime),
    }

    return await client.get("appointmentService/load",params=params)

def _build_appointment_body(
        patient_uuid: str,
        service_uuid: str,
        start_datetime: datetime,
        end_datetime: datetime,
        appointment_kind: str,
        provider_uuids: list[str] | None,
        location_uuid: str | None
) -> dict:
    
    body ={
        "patientUuid": patient_uuid,
        "serviceUuid": service_uuid,
        "startDateTime": to_openmrs_datetime(start_datetime),
        "endDateTime": to_openmrs_datetime(end_datetime),
        "appointmentKind": appointment_kind,
    }

    if location_uuid is not None:
        body["locationUuid"] = location_uuid
    if provider_uuids:
        body["providers"] = [{"uuid":provider_uuid} for provider_uuid in provider_uuids]
    
    return body

@mcp.tool()
async def check_appointment_conflicts(
    patient_uuid:str,
    service_uuid:str,
    start_datetime: datetime,
    end_datetime: datetime,
    appointment_kind:Literal["Scheduled","WalkIn"] = "Scheduled",
    provider_uuids: list[str] | None = None,
    location_uuid: str | None = None,
) -> dict:
    
    body = _build_appointment_body(
        patient_uuid,service_uuid,start_datetime,end_datetime,appointment_kind,provider_uuids,location_uuid
    )

    return await client.post("appointments/conflicts",json=body)

@mcp.tool()
async def create_appointment(
    patient_uuid: str,
    service_uuid: str,
    start_datetime:datetime,
    end_datetime: datetime,
    appointment_kind: Literal["Scheduled","WalkIn"] = "Scheduled",
    provider_uuids: list[str] | None = None,
    location_uuid: str | None =None,
) -> dict:
    body = _build_appointment_body(
        patient_uuid,service_uuid,start_datetime,end_datetime,appointment_kind,provider_uuids,location_uuid,
    )
    return await client.post("appointment",json=body)
