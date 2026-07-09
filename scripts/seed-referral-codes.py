"""
Add referral codes to existing patient users that don't have one yet.
"""
import asyncio
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma


def generate_code() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(8))
    return f"SAHA-{suffix}"


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    users = await db.user.find_many(
        where={"role": "PATIENT", "referralCode": None}
    )

    if not users:
        print("All patients already have referral codes.")
        await db.disconnect()
        return

    for u in users:
        code = generate_code()
        await db.user.update(
            where={"id": u.id}, data={"referralCode": code}
        )
        print(f"ADDED referral code {code} → {u.email}")

    await db.disconnect()
    print(f"\n{len(users)} referral codes added.")


if __name__ == "__main__":
    asyncio.run(main())
