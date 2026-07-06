import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

SESSIONS = [
    {
        "therapist_email": "aarati@test.com",
        "patient_email": "ramesh@test.com",
        "date": datetime(2026, 7, 2),
        "time": "10:00",
        "type": "HOME_VISIT",
        "status": "SCHEDULED",
        "address": "Baluwatar, Kathmandu",
        "fee": 1500,
    },
    {
        "therapist_email": "bibek@test.com",
        "patient_email": "sita@test.com",
        "date": datetime(2026, 7, 5),
        "time": "16:00",
        "type": "HOME_VISIT",
        "status": "SCHEDULED",
        "address": "Jhamsikhel, Lalitpur",
        "fee": 1200,
    },
    {
        "therapist_email": "aarati@test.com",
        "patient_email": "ramesh@test.com",
        "date": datetime(2026, 6, 20),
        "time": "11:00",
        "type": "HOME_VISIT",
        "status": "COMPLETED",
        "address": "Baluwatar, Kathmandu",
        "fee": 1500,
    },
    {
        "therapist_email": "sushmita@test.com",
        "patient_email": "hari@test.com",
        "date": datetime(2026, 6, 18),
        "time": "09:00",
        "type": "HOME_VISIT",
        "status": "COMPLETED",
        "address": "Bhaktapur",
        "fee": 1400,
    },
    {
        "therapist_email": "bibek@test.com",
        "patient_email": "sita@test.com",
        "date": datetime(2026, 6, 12),
        "time": "14:00",
        "type": "HOME_VISIT",
        "status": "CANCELLED",
        "address": "Jhamsikhel, Lalitpur",
        "fee": 1200,
    },
]


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    for s in SESSIONS:
        therapist_user = await db.user.find_unique(where={"email": s["therapist_email"]})
        if not therapist_user:
            print(f"SKIP session — therapist user not found ({s['therapist_email']})")
            continue

        therapist = await db.therapist.find_unique(where={"userId": therapist_user.id})
        if not therapist:
            print(f"SKIP session — therapist profile not found for {s['therapist_email']}")
            continue

        patient = await db.user.find_unique(where={"email": s["patient_email"]})
        if not patient:
            print(f"SKIP session — patient not found ({s['patient_email']})")
            continue

        existing = await db.session.find_first(
            where={
                "therapistId": therapist.id,
                "patientId": patient.id,
                "date": s["date"],
                "time": s["time"],
            }
        )
        if existing:
            print(f"SKIP session — {s['therapist_email']} / {s['patient_email']} @ {s['date']} {s['time']} (already exists)")
            continue

        session = await db.session.create(
            data={
                "therapistId": therapist.id,
                "patientId": patient.id,
                "date": s["date"],
                "time": s["time"],
                "type": s["type"],
                "status": s["status"],
                "address": s["address"],
                "fee": s["fee"],
            }
        )
        print(f"CREATED session — {s['therapist_email']} / {s['patient_email']} @ {s['date']} {s['time']} (id={session.id})")

    await db.disconnect()
    print("\nSessions seeded.")


if __name__ == "__main__":
    asyncio.run(main())
