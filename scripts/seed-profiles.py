import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    therapist_users = await db.user.find_many(where={"role": "THERAPIST"})
    for user in therapist_users:
        existing = await db.therapist.find_unique(where={"userId": user.id})
        if existing:
            print(f"SKIP  therapist profile for {user.email} — already exists")
            continue
        await db.therapist.create(data={
            "userId": user.id,
            "name": user.name,
            "specialty": user.specialty or "General",
            "city": user.city or "Kathmandu",
            "gender": "Male",
            "price": 1000.0,
            "experience": 1,
            "bio": "",
        })
        print(f"CREATED therapist profile for {user.email}")

    patient_users = await db.user.find_many(where={"role": "PATIENT"})
    for user in patient_users:
        existing = await db.patientprofile.find_unique(where={"userId": user.id})
        if existing:
            print(f"SKIP  patient profile for {user.email} — already exists")
            continue
        await db.patientprofile.create(data={
            "userId": user.id,
            "name": user.name,
            "phone": user.phone or "",
            "city": user.city or "Kathmandu",
        })
        print(f"CREATED patient profile for {user.email}")

    await db.disconnect()
    print("\nProfiles seeded.")


if __name__ == "__main__":
    asyncio.run(main())
