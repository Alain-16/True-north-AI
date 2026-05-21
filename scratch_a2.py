import asyncio
from datetime import datetime, timedelta, timezone

from mcp_server.tools.patient import (
      get_patient_by_identifier,
      get_patient_lab_results,
      get_patient_prescriptions,
  )
from mcp_server.tools.appointment import (
      get_upcoming_appointments,
      get_hospital_busyness_patterns,
  )


async def main():
      # Resolve the test patient → UUID (swap in your real identifier)
      patient = await get_patient_by_identifier("ABC200000")
      patient_uuid = patient["uuid"]
      print("\npatient:", patient)

      # 1. Upcoming appointments
      appts = await get_upcoming_appointments(patient_uuid)
      print(f"\n[1] upcoming appointments ({len(appts)}):", appts)

      # 2. Hospital busyness — a 30-day window
      now = datetime.now(timezone.utc)
      summary = await get_hospital_busyness_patterns(now, now + timedelta(days=30))
      print(f"\n[2] busyness summary ({len(summary)} services):", summary)

      # 3. Lab results (observations)
      obs = await get_patient_lab_results(patient_uuid)
      print(f"\n[3] observations ({len(obs)}):", obs)

      # 4. Prescriptions (drug orders)
      rx = await get_patient_prescriptions(patient_uuid)
      print(f"\n[4] prescriptions ({len(rx)}):", rx)


asyncio.run(main())