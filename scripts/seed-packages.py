import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

SEED_DATA = [
    {
        "name": "Stroke & Neuro Recovery",
        "tag": "Most requested from abroad",
        "icon": "Brain",
        "price": 24000,
        "cadence": "per month \u00b7 12 sessions",
        "blurb": "Structured neuro-rehab for stroke, Parkinson's and spinal cord recovery at home.",
        "points": [
            "Gait, balance and speech-support coordination",
            "Weekly progress report shared with family abroad",
            "Same therapist for the whole plan",
        ],
        "featured": True,
        "sortOrder": 1,
    },
    {
        "name": "Sports Injury Comeback",
        "tag": "Return to play",
        "icon": "Activity",
        "price": 16000,
        "cadence": "per month \u00b7 8 sessions",
        "blurb": "ACL, rotator cuff, ankle and hamstring rehab with a graded return-to-sport plan.",
        "points": [
            "Strength and mobility testing at week 1 and 4",
            "Home exercise plan in the app",
            "Sports physio with clinic experience",
        ],
        "featured": False,
        "sortOrder": 2,
    },
    {
        "name": "Elderly Mobility & Fall Prevention",
        "tag": "For parents at home",
        "icon": "HeartHandshake",
        "price": 19000,
        "cadence": "per month \u00b7 10 sessions",
        "blurb": "Keep aging parents walking safely \u2014 strength, balance and home-safety guidance.",
        "points": [
            "Home hazard check on the first visit",
            "Family video call after every 3rd session",
            "Caregiver training included",
        ],
        "featured": False,
        "sortOrder": 3,
    },
]


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    for item in SEED_DATA:
        existing = await db.package.find_first(where={"name": item["name"]})
        if existing:
            print(f"SKIP  {item['name']} -- already exists (id={existing.id})")
            continue

        created = await db.package.create(data=item)
        print(f"CREATED {created.name} -- id={created.id}, price={created.price}")

    await db.disconnect()
    print("\nPackages seeded.")


if __name__ == "__main__":
    asyncio.run(main())
