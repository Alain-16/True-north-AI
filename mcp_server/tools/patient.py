from mcp_server.app import mcp
from mcp_server.openmrs_client import client

@mcp.tool()
async def get_patient_by_identifier(identifier:str)-> dict:
    data = await client.get("patient",params={"identifier":identifier})

    results = data.get("results",[])
    if not results:
        raise ValueError(f"No patient found with identifier '{identifier}'")
    patient = results[0]
    return {"uuid":patient["uuid"],"display":patient["display"]}