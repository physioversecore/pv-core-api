import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    # Grab seeded packages keyed by "sessions count" (there should be 12/8/10)
    packages = await db.package.find_many()
    if not packages:
        print("No packages found. Run `uv run python scripts/seed-packages.py` first.")
        await db.disconnect()
        return

    # Grab patient users
    patients = await db.user.find_many(where={"role": "PATIENT"})
    if not patients:
        print("No patients found. Run `uv run python scripts/seed-users.py` first.")
        await db.disconnect()
        return

    now = datetime.now(timezone.utc)
    created = 0
    skipped = 0

    # Give the first N patients (excluding ones who already have any purchase)
    for i, patient in enumerate(patients[: min(3, len(patients))]):
        existing = await db.packagepurchase.find_first(where={"userId": patient.id})
        if existing:
            skipped += 1
            print(f"SKIP  {patient.name} -- already has a purchase")
            continue

        pkg = packages[i % len(packages)]
        sessions_total = pkg.sessionCount
        # Vary usage so the dashboard/analytics look populated:
        sessions_used = min(sessions_total, (i * 2) + 1)
        status = "ACTIVE" if sessions_used < sessions_total else "DEPLETED"
        expires_at = now + timedelta(days=pkg.validityDays)

        payment = await db.payment.create(
            data={
                "userId": patient.id,
                "amount": float(pkg.price),
                "status": "COMPLETED",
                "method": "ESEWA",
                "currency": "NPR",
                "platformFee": 0,
                "paymentType": "PACKAGE",
            }
        )

        purchase = await db.packagepurchase.create(
            data={
                "userId": patient.id,
                "packageId": pkg.id,
                "paymentId": payment.id,
                "sessionsTotal": sessions_total,
                "sessionsUsed": sessions_used,
                "status": status,
                "purchasedAt": now - timedelta(days=2),
                "expiresAt": expires_at,
            }
        )
        created += 1
        print(
            f"CREATED purchase for {patient.name} -- {pkg.name} "
            f"({sessions_used}/{sessions_total} used, {status})"
        )

    await db.disconnect()
    print(f"\nPackage purchases seeded. Created={created}, Skipped={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
