import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

SERVICES = [
    # Clinical Services
    {"name": "Sports Injury Rehab", "description": "ACL, rotator cuff, sprain recovery.", "category": "CLINICAL", "iconName": "Activity", "sortOrder": 1},
    {"name": "Post-Surgery Rehab", "description": "Knee, hip, and joint replacement recovery.", "category": "CLINICAL", "iconName": "HeartPulse", "sortOrder": 2},
    {"name": "Neuro Rehab", "description": "Stroke, Parkinson's, spinal cord injury rehabilitation.", "category": "CLINICAL", "iconName": "Brain", "sortOrder": 3},
    {"name": "Pediatric & Elderly Care", "description": "Developmental delays, geriatric care.", "category": "CLINICAL", "iconName": "Baby", "sortOrder": 4},
    {"name": "Orthopedic Rehab", "description": "Fracture recovery, joint mobility restoration.", "category": "CLINICAL", "iconName": "Bone", "sortOrder": 5},
    {"name": "Strength & Conditioning", "description": "Muscle strengthening, fitness recovery.", "category": "CLINICAL", "iconName": "Dumbbell", "sortOrder": 6},
    # Shop Services
    {"name": "Home-visit Booking", "description": "Therapists who come to you.", "category": "SHOP", "iconName": "Stethoscope", "sortOrder": 7},
    {"name": "Equipment Rental", "description": "Wheelchairs, crutches, TENS units.", "category": "SHOP", "iconName": "ShoppingBag", "sortOrder": 8},
    {"name": "Medicines", "description": "Recovery medications delivered to your door.", "category": "SHOP", "iconName": "Pill", "sortOrder": 9},
    {"name": "Recovery Nutrition", "description": "Supplements & meal plans for recovery.", "category": "SHOP", "iconName": "Apple", "sortOrder": 10},
]


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    for s in SERVICES:
        existing = await db.service.find_first(where={"name": s["name"]})
        if existing:
            print(f"SKIP  {s['name']} — already exists (id={existing.id})")
            continue

        service = await db.service.create(data=s)
        print(f"CREATED {service.name} — id={service.id}, category={service.category}")

    await db.disconnect()
    print("\nServices seeded.")


if __name__ == "__main__":
    asyncio.run(main())
