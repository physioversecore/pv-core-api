import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma


PATIENT_PROFILES = {
    "patient@test.com": {
        "name": "John Doe",
        "phone": "9841234567",
        "city": "Kathmandu",
        "address": "Baneshwor, Kathmandu",
        "history": "Chronic back pain, 6 months",
        "gender": "Male",
        "notifEmail": True,
        "notifSms": False,
    },
    "ramesh@test.com": {
        "name": "Ramesh Adhikari",
        "phone": "9851234567",
        "city": "Lalitpur",
        "address": "Jawalakhel, Lalitpur",
        "history": "Post-surgery knee rehabilitation",
        "gender": "Male",
        "notifEmail": True,
        "notifSms": False,
    },
    "sita@test.com": {
        "name": "Sita Lama",
        "phone": "9861234567",
        "city": "Kathmandu",
        "address": "Lazimpat, Kathmandu",
        "history": "Shoulder impingement",
        "gender": "Female",
        "notifEmail": True,
        "notifSms": False,
    },
    "hari@test.com": {
        "name": "Hari Pradhan",
        "phone": "9871234567",
        "city": "Bhaktapur",
        "address": "Suryamadhi, Bhaktapur",
        "history": "Sports injury - ankle sprain",
        "gender": "Male",
        "notifEmail": True,
        "notifSms": False,
    },
}


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    for email, data in PATIENT_PROFILES.items():
        user = await db.user.find_unique(where={"email": email})
        if not user:
            print(f"SKIP  {email} — user not found")
            continue

        existing = await db.patientprofile.find_unique(where={"userId": user.id})
        if existing:
            print(f"SKIP  {email} — profile already exists")
            continue

        await db.patientprofile.create(data={"userId": user.id, **data})
        print(f"CREATED profile for {email}")

    await db.disconnect()
    print("\nPatient profiles seeded.")


if __name__ == "__main__":
    asyncio.run(main())
