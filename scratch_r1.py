
import asyncio
import json

from agent.subgraphs.reports import shape_lab_result, shape_prescription
from mcp_server.openmrs_client import client

# ABC200000 - John kalisa, from the real /order response
PATIENT_UUID = "99e6502c-2ea6-4f10-9a4f-4669e0aa07fc"


def _show(label: str, obj) -> None:
    print(f"\n--- {label} ---")
    print(json.dumps(obj, indent=2, default=str))


async def main() -> None:
    # ── Prescriptions ──────────────────────────────────────────────────────
    orders = (await client.get(
        "order",
        params={"patient": PATIENT_UUID, "type": "drugorder", "v": "full"},
    )).get("results", [])
    print(f"{len(orders)} drug order(s)")
    for o in orders[:3]:
        _show(f"rx: {o.get('orderNumber')}", shape_prescription(o))

    # ── Lab results ────────────────────────────────────────────────────────
    obs_list = (await client.get(
        "obs",
        params={"patient": PATIENT_UUID, "v": "full"},
    )).get("results", [])
    print(f"\n{len(obs_list)} observation(s)")
    for ob in obs_list[:3]:
        # Fetch the concept too, to exercise the units + reference_range path.
        concept_uuid = (ob.get("concept") or {}).get("uuid")
        concept = None
        if concept_uuid:
            concept = await client.get(f"concept/{concept_uuid}", params={"v": "full"})
        _show(f"lab: {(ob.get('concept') or {}).get('display')}",
              shape_lab_result(ob, concept))

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
