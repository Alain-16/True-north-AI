from mcp_server.app import mcp
from mcp_server.openmrs_client import client

@mcp.tool()
async def list_specialities()-> list:
    return await client.get("speciality/all")

@mcp.tool()
async def search_services(
    speciality_uuid: str | None=None,
    name: str | None = None,
    location_uuid: str | None = None,
) -> list:
    
    params = {
        "speciality_uuid": speciality_uuid,
        "name":name,
        "locationUuid":location_uuid,
    }
    params = {k:v for k,v in params.items() if v is not None}
    return await client.get("appointmentService/search",params=params)