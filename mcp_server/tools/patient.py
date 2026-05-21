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

@mcp.tool()
async def get_patient_lab_results(patient_uuid: str)-> list:

    data = await client.get("obs",params={"patient":patient_uuid,"v":"full"})
    return data.get("results",[])


@mcp.tool()
async def get_patient_prescriptions(patient_uuid:str)-> list:

    data = await client.get(
        "order",
        params={"patient":patient_uuid,"type":"drugorder","v":"full"}

    )
    return data.get("result",[])