import asyncio
from datetime import datetime, timedelta, timezone

from mcp_server.tools.patient import get_patient_by_identifier
from mcp_server.tools.appointment import (
      list_specialities,
      search_services,
      get_service_load,
      check_appointment_conflicts,
      create_appointment,
  )


async def main():
      # 1. Discovery — no input needed
      specialities = await list_specialities()
      print("\n[1] specialities:", specialities)
      if not specialities:
          print("No specialities configured in OpenMRS — stopping.")
          return
      speciality_uuid = specialities[0]["uuid"]

      # 2. Services under the first speciality
      services = await search_services(speciality_uuid=speciality_uuid)
      print("\n[2] services:", services)
      if not services:
          print("No services for that speciality — stopping.")
          return
      service = services[0]
      service_uuid = service["uuid"]

      # 3. Capacity for a one-day window
      day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
      day_end = day_start + timedelta(days=1)
      load = await get_service_load(service_uuid, day_start, day_end)
      print(f"\n[3] load today: {load} / cap {service.get('maxAppointmentsLimit')}")

      # 4. Patient lookup — REPLACE with a real identifier from your instance
      patient = await get_patient_by_identifier("ABC200000")
      print("\n[4] patient:", patient)
      patient_uuid = patient["uuid"]

      # 5. Conflict check for a future slot
      start = day_start + timedelta(days=1, hours=9)
      end = start + timedelta(minutes=service.get("durationMins") or 30)
      conflicts = await check_appointment_conflicts(patient_uuid, service_uuid, start, end)
      print("\n[5] conflicts:", conflicts)

      
      appt = await create_appointment(patient_uuid, service_uuid, start, end)
      print("\n[6] created:", appt)


asyncio.run(main())