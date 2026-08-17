import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

SEED_DATA = [
    {
        "name": "Chhetrapati Clinic",
        "area": "Chhetrapati",
        "city": "Kathmandu",
        "address": "Chhetrapati, Kathmandu (near Indra Chowk)",
        "services": ["Orthopedic physio", "Post-surgery rehab", "Manual therapy"],
        "phone": "+977 01-4261234",
        "hours": "Sun\u2013Fri: 8:00 AM \u2013 6:00 PM",
    },
    {
        "name": "Hamro Physio Clinic",
        "area": "Maharajgunj",
        "city": "Kathmandu",
        "address": "Maharajgunj, Kathmandu (near TUTH)",
        "services": ["Neuro rehab", "Pediatric physiotherapy", "Geriatric care"],
        "phone": "+977 01-4720567",
        "hours": "Sun\u2013Fri: 9:00 AM \u2013 7:00 PM",
    },
    {
        "name": "Move Mobility Healthy Life",
        "area": "Kaladhara",
        "city": "Kathmandu",
        "address": "Kaladhara, Kathmandu",
        "services": ["Sports injury rehab", "Strength & conditioning", "Chronic pain management"],
        "phone": "+977 01-4419988",
        "hours": "Sun\u2013Fri: 7:00 AM \u2013 8:00 PM",
    },
    {
        "name": "Patan Physiotherapy Centre",
        "area": "Lagankhel",
        "city": "Lalitpur",
        "address": "Lagankhel, Lalitpur (near Patan Hospital)",
        "services": ["Post-op rehab", "Cardiac physiotherapy", "Respiratory care"],
        "phone": "+977 01-5522310",
        "hours": "Sun\u2013Fri: 8:00 AM \u2013 5:00 PM",
    },
    {
        "name": "Pokhara Rehabilitation Hub",
        "area": "Mahendrapul",
        "city": "Pokhara",
        "address": "Mahendrapul, Pokhara",
        "services": ["Sports injury rehab", "Neuro rehab", "Pediatric physiotherapy"],
        "phone": "+977 061-521456",
        "hours": "Sun\u2013Fri: 9:00 AM \u2013 6:00 PM",
    },
]


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    for item in SEED_DATA:
        existing = await db.clinic.find_first(where={"name": item["name"]})
        if existing:
            print(f"SKIP  {item['name']} -- already exists (id={existing.id})")
            continue

        created = await db.clinic.create(data=item)
        print(f"CREATED {created.name} -- id={created.id}, city={created.city}")

    await db.disconnect()
    print("\nClinics seeded.")


if __name__ == "__main__":
    asyncio.run(main())
