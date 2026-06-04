from mcp_server.app import mcp
from mcp_server.openmrs_client import client


_PHONE_ATTR_NAMES = {"Telephone Number","Phone number","Mobile","Contact Number"}
_EMAIL_ATTR_NAMES = {"Email","Email Address","Email address"}

def _person_attr(person: dict, names: set[str]) -> str | None:
    for attr in person.get("attributes") or []:
        display = (attr.get("attributeType") or {}).get("display")
        if display in names:
            return attr.get("value") or None
        return None

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
    return data.get("results",[])

@mcp.tool()
async def get_obs_by_uuid(obs_uuid:str)-> dict:
    return await client.get(f"obs/{obs_uuid}",params={"v":"full"})

@mcp.tool()
async def get_order_by_uuid(order_uuid:str)-> dict:
    return await client.get(f"order/{order_uuid}", params={"v":"full"})

@mcp.tool()
async def get_concept_by_uuid(concept_uuid:str)->dict:
    return await client.get(f"concept/{concept_uuid}",params={"v":"full"})

@mcp.tool()
async def get_patient_by_uuid(patient_uuid: str) -> dict:
      data = await client.get(f"patient/{patient_uuid}", params={"v": "full"})
      identifiers = data.get("identifiers") or []
      person = data.get("person") or {}
      return {
          "uuid": data.get("uuid"),
          "identifier": identifiers[0].get("identifier") if identifiers else None,
          "age": person.get("age"),
          "gender": person.get("gender"),
          "email":_person_attr(person,_EMAIL_ATTR_NAMES),
          "phone":_person_attr(person,_PHONE_ATTR_NAMES),
      }
