import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

THERAPISTS = [
    {
        "email": "therapist@test.com",
        "name": "Dr. Jane Smith",
        "specialty": "Physical Therapy",
        "city": "Kathmandu",
        "gender": "Female",
        "rating": 4.8,
        "reviews": 42,
        "price": 1500.0,
        "experience": 10,
        "bio": "Experienced physical therapist specializing in sports injuries and rehabilitation.",
    },
    {
        "email": "aarati@test.com",
        "name": "Dr. Aarati Shrestha",
        "specialty": "Sports & post-surgery",
        "city": "Kathmandu",
        "gender": "Female",
        "rating": 4.9,
        "reviews": 128,
        "price": 1500.0,
        "experience": 8,
        "bio": "Specialist in ACL and rotator cuff rehab with 8+ years of home-visit experience.",
    },
    {
        "email": "bibek@test.com",
        "name": "Dr. Bibek Thapa",
        "specialty": "Musculoskeletal",
        "city": "Lalitpur",
        "gender": "Male",
        "rating": 4.8,
        "reviews": 96,
        "price": 1200.0,
        "experience": 6,
        "bio": "Manual therapy and dry needling specialist.",
    },
    {
        "email": "sushmita@test.com",
        "name": "Dr. Sushmita Rai",
        "specialty": "Geriatric & neuro",
        "city": "Kathmandu",
        "gender": "Female",
        "rating": 4.9,
        "reviews": 142,
        "price": 1400.0,
        "experience": 10,
        "bio": "Stroke and Parkinson's rehab for elderly patients.",
    },
    {
        "email": "nirajan@test.com",
        "name": "Dr. Nirajan Karki",
        "specialty": "Pediatric rehab",
        "city": "Pokhara",
        "gender": "Male",
        "rating": 4.7,
        "reviews": 67,
        "price": 1300.0,
        "experience": 5,
        "bio": "Cerebral palsy and developmental delays.",
    },
    {
        "email": "sabina@test.com",
        "name": "Dr. Sabina Gurung",
        "specialty": "Neurological",
        "city": "Bhaktapur",
        "gender": "Female",
        "rating": 4.8,
        "reviews": 84,
        "price": 1600.0,
        "experience": 9,
        "bio": "Post-stroke and spinal cord rehabilitation.",
    },
    {
        "email": "rajan@test.com",
        "name": "Dr. Rajan Magar",
        "specialty": "Post-operative",
        "city": "Chitwan",
        "gender": "Male",
        "rating": 4.6,
        "reviews": 51,
        "price": 1100.0,
        "experience": 4,
        "bio": "Post-op knee and hip recovery.",
    },
    {
        "email": "priya@test.com",
        "name": "Dr. Priya Tamang",
        "specialty": "General",
        "city": "Biratnagar",
        "gender": "Female",
        "rating": 4.7,
        "reviews": 73,
        "price": 1000.0,
        "experience": 5,
        "bio": "General home physiotherapy and pain management.",
    },
    {
        "email": "anil@test.com",
        "name": "Dr. Anil Shakya",
        "specialty": "Sports & post-surgery",
        "city": "Lalitpur",
        "gender": "Male",
        "rating": 4.9,
        "reviews": 110,
        "price": 1700.0,
        "experience": 11,
        "bio": "Former national team physio.",
    },
]


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    for t in THERAPISTS:
        user = await db.user.find_unique(where={"email": t["email"]})
        if not user:
            print(f"SKIP  {t['name']} — user not found ({t['email']})")
            continue

        existing = await db.therapist.find_unique(where={"userId": user.id})
        if existing:
            print(f"SKIP  {t['name']} — therapist profile already exists (id={existing.id})")
            continue

        data = {k: v for k, v in t.items() if k != "email"}
        therapist = await db.therapist.create(data={"userId": user.id, **data})
        print(f"CREATED Therapist profile — {t['name']} (id={therapist.id})")

    await db.disconnect()
    print("\nTherapists seeded.")


if __name__ == "__main__":
    asyncio.run(main())
