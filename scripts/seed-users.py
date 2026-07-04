import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt
from prisma import Prisma


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


MOCK_USERS = [
    {
        "email": "patient@test.com",
        "password": "password123",
        "name": "John Doe",
        "role": "PATIENT",
        "city": "Kathmandu",
        "phone": "9800000001",
        "status": "APPROVED",
    },
    {
        "email": "therapist@test.com",
        "password": "password123",
        "name": "Dr. Jane Smith",
        "role": "THERAPIST",
        "city": "Kathmandu",
        "phone": "9800000002",
        "specialty": "Physical Therapy",
        "status": "APPROVED",
    },
    {
        "email": "admin@test.com",
        "password": "password123",
        "name": "Admin User",
        "role": "ADMIN",
        "city": "Kathmandu",
        "phone": "9800000003",
        "status": "APPROVED",
    },
]

MOCK_THERAPIST = {
    "name": "Dr. Jane Smith",
    "specialty": "Physical Therapy",
    "city": "Kathmandu",
    "gender": "Female",
    "rating": 4.8,
    "reviews": 42,
    "price": 1500.0,
    "experience": 10,
    "bio": "Experienced physical therapist specializing in sports injuries and rehabilitation.",
}


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    for user_data in MOCK_USERS:
        email = user_data["email"]
        existing = await db.user.find_unique(where={"email": email})
        if existing:
            print(f"SKIP  {email} — already exists (id={existing.id})")
            continue

        password = user_data.pop("password")
        user_data["password"] = hash_password(password)
        user = await db.user.create(data=user_data)
        print(f"CREATED {email} — id={user.id}, role={user.role}")

        if user.role == "THERAPIST":
            existing_therapist = await db.therapist.find_unique(where={"userId": user.id})
            if not existing_therapist:
                therapist_data = {**MOCK_THERAPIST, "userId": user.id}
                therapist = await db.therapist.create(data=therapist_data)
                print(f"CREATED Therapist profile — id={therapist.id}")

    await db.disconnect()
    print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(main())
