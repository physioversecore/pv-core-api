import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt
from prisma import Prisma

import secrets
import string

REFERRAL_CODES: dict[str, str] = {}


def _make_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "SAHA-" + "".join(secrets.choice(chars) for _ in range(8))


def _get_code(email: str) -> str:
    if email not in REFERRAL_CODES:
        REFERRAL_CODES[email] = _make_code()
    return REFERRAL_CODES[email]


USERS = [
    {"email": "patient@test.com",     "password": "password123", "name": "John Doe",         "role": "PATIENT",   "city": "Kathmandu",  "phone": "9800000001", "status": "APPROVED"},
    {"email": "therapist@test.com",   "password": "password123", "name": "Dr. Jane Smith",   "role": "THERAPIST", "city": "Kathmandu",  "phone": "9800000002", "status": "APPROVED"},
    {"email": "admin@test.com",       "password": "password123", "name": "Admin User",       "role": "ADMIN",     "city": "Kathmandu",  "phone": "9800000003", "status": "APPROVED"},
    {"email": "ramesh@test.com",      "password": "password123", "name": "Ramesh Adhikari",  "role": "PATIENT",   "city": "Kathmandu",  "phone": "9800000004", "status": "APPROVED"},
    {"email": "sita@test.com",        "password": "password123", "name": "Sita Lama",        "role": "PATIENT",   "city": "Lalitpur",   "phone": "9800000005", "status": "APPROVED"},
    {"email": "hari@test.com",        "password": "password123", "name": "Hari Pradhan",     "role": "PATIENT",   "city": "Bhaktapur",  "phone": "9800000006", "status": "APPROVED"},
    {"email": "aarati@test.com",      "password": "password123", "name": "Dr. Aarati Shrestha", "role": "THERAPIST", "city": "Kathmandu",  "phone": "9800000007", "status": "APPROVED"},
    {"email": "bibek@test.com",       "password": "password123", "name": "Dr. Bibek Thapa",  "role": "THERAPIST", "city": "Lalitpur",   "phone": "9800000008", "status": "APPROVED"},
    {"email": "sushmita@test.com",    "password": "password123", "name": "Dr. Sushmita Rai", "role": "THERAPIST", "city": "Kathmandu",  "phone": "9800000009", "status": "APPROVED"},
    {"email": "nirajan@test.com",     "password": "password123", "name": "Dr. Nirajan Karki","role": "THERAPIST", "city": "Pokhara",    "phone": "9800000010", "status": "APPROVED"},
    {"email": "sabina@test.com",      "password": "password123", "name": "Dr. Sabina Gurung","role": "THERAPIST", "city": "Bhaktapur",  "phone": "9800000011", "status": "APPROVED"},
    {"email": "rajan@test.com",       "password": "password123", "name": "Dr. Rajan Magar",  "role": "THERAPIST", "city": "Chitwan",    "phone": "9800000012", "status": "APPROVED"},
    {"email": "priya@test.com",       "password": "password123", "name": "Dr. Priya Tamang", "role": "THERAPIST", "city": "Biratnagar", "phone": "9800000013", "status": "APPROVED"},
    {"email": "anil@test.com",        "password": "password123", "name": "Dr. Anil Shakya",  "role": "THERAPIST", "city": "Lalitpur",   "phone": "9800000014", "status": "APPROVED"},
]


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    created_ids = {}
    for data in USERS:
        email = data["email"]
        existing = await db.user.find_unique(where={"email": email})
        if existing:
            print(f"SKIP  {email} — already exists (id={existing.id})")
            if existing.role == "PATIENT" and not existing.referralCode:
                code = _get_code(email)
                await db.user.update(where={"id": existing.id}, data={"referralCode": code})
                print(f"  → added referral code {code}")
            created_ids[email] = existing.id
            continue

        password = data.pop("password")
        data["password"] = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        if data.get("role") == "PATIENT":
            data["referralCode"] = _get_code(email)
        user = await db.user.create(data=data)
        print(f"CREATED {email} — id={user.id}, role={user.role}")
        created_ids[email] = user.id

    await db.disconnect()
    print("\nUsers seeded.")


if __name__ == "__main__":
    asyncio.run(main())
