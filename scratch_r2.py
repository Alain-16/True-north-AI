"""End-to-end check for the ReportSubgraph (Unit 2), run on REAL OpenMRS UUIDs.

Needs the MCP SSE server RUNNING (so get_obs_by_uuid / get_order_by_uuid /
get_concept_by_uuid / get_patient_by_uuid are registered) and OpenMRS up.

Run:  ./venv/bin/python scratch_r2.py
"""

import asyncio

from agent.mcp_client import mcp_client
from agent.subgraphs.reports import build_report_subgraph

OPENMRS_PATIENT_ID = "ABC200002"
PATIENT_ID = "test"

# A real drug order from the live run — the one that fell back to low-confidence.
PRESCRIPTION_UUID = "2aa85a92-851a-489f-bc34-514641ec4273"
# A diagnosis obs (value null) exercises the skip-gate; swap for a real lab obs
# uuid to test the full lab path.
DIAGNOSIS_OBS_UUID = "409d2720-0e5d-4b02-96b1-00dd4db2dce2"


def _print(label: str, state: dict) -> None:
    print(f"\n========== {label} ==========")
    print("skip_reason:   ", state.get("skip_reason"))
    print("classification:", state.get("classification"))
    print("is_critical:   ", state.get("is_critical"))
    print("confidence:    ", state.get("confidence"))
    print("shaped:        ", state.get("shaped"))
    resp = state.get("response")
    if resp:
        print("response.type: ", resp["type"])
        print("content:\n" + resp["content"])
    print("profile_extraction:", state.get("profile_extraction"))


async def _run(graph, resource_uuid: str, resource_type: str, label: str) -> None:
    state = await graph.ainvoke({
        "resource_uuid":      resource_uuid,
        "resource_type":      resource_type,
        "openmrs_patient_id": OPENMRS_PATIENT_ID,
        "patient_id":         PATIENT_ID,
        "channel":            "web",
    })
    _print(label, state)


async def main() -> None:
    await mcp_client.connect()
    try:
        graph = build_report_subgraph()
        await _run(graph, PRESCRIPTION_UUID, "prescription", "PRESCRIPTION (real order)")
        # await _run(graph, DIAGNOSIS_OBS_UUID, "lab", "LAB skip-gate")
    finally:
        await mcp_client.close()


if __name__ == "__main__":
    asyncio.run(main())
