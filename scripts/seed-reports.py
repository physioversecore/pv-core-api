import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

REPORTS = [
    {
        "patient_email": "ramesh@test.com",
        "therapist_email": "aarati@test.com",
        "session_date": datetime(2026, 6, 20),
        "title": "Progress report — week 4",
        "content": "Range of motion improving. Patient can now flex knee to 110°. Continue with quad sets and hamstring stretches.",
    },
    {
        "patient_email": "hari@test.com",
        "therapist_email": "sushmita@test.com",
        "session_date": datetime(2026, 6, 18),
        "title": "Session note — Stroke rehab",
        "content": "Upper limb coordination exercises introduced. Patient responds well to mirror therapy.",
    },
]


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    for r in REPORTS:
        patient = await db.user.find_unique(where={"email": r["patient_email"]})
        if not patient:
            print(f"SKIP report — patient not found ({r['patient_email']})")
            continue

        therapist_user = await db.user.find_unique(where={"email": r["therapist_email"]})
        if not therapist_user:
            print(f"SKIP report — therapist user not found ({r['therapist_email']})")
            continue

        therapist = await db.therapist.find_unique(where={"userId": therapist_user.id})
        if not therapist:
            print(f"SKIP report — therapist profile not found for {r['therapist_email']}")
            continue

        session = await db.session.find_first(
            where={
                "therapistId": therapist.id,
                "patientId": patient.id,
                "date": r["session_date"],
            }
        )

        existing = await db.report.find_first(
            where={"patientId": patient.id, "title": r["title"]}
        )
        if existing:
            print(f"SKIP report — '{r['title']}' already exists (id={existing.id})")
            continue

        data = {
            "patientId": patient.id,
            "title": r["title"],
            "content": r["content"],
        }
        if session:
            data["sessionId"] = session.id

        report = await db.report.create(data=data)
        print(f"CREATED report — '{r['title']}' (id={report.id})")

    await db.disconnect()
    print("\nReports seeded.")


if __name__ == "__main__":
    asyncio.run(main())
