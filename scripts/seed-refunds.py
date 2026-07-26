import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

REFUNDS = [
    {
        "patient_email": "patient@test.com",
        "booking_id": "BK-2026-001",
        "amount": 1500.0,
        "reason": "NO_SHOW",
        "status": "PENDING",
        "source": "PATIENT_SUBMITTED",
        "notes": "Patient reported therapist did not arrive for the scheduled session.",
    },
    {
        "patient_email": "ramesh@test.com",
        "booking_id": "BK-2026-002",
        "amount": 1200.0,
        "reason": "DOUBLE_CHARGE",
        "status": "APPROVED",
        "source": "PATIENT_SUBMITTED",
        "notes": "Patient was charged twice for the same session on Jun 20.",
        "resolved_days_ago": 3,
    },
    {
        "patient_email": "sita@test.com",
        "booking_id": "BK-2026-003",
        "amount": 850.0,
        "reason": "SERVICE_QUALITY",
        "status": "DENIED",
        "source": "PATIENT_SUBMITTED",
        "denyReason": "Service was delivered as scheduled. No quality issue found after review.",
        "notes": "Patient claimed session was cut short.",
        "resolved_days_ago": 5,
    },
    {
        "patient_email": "hari@test.com",
        "booking_id": "BK-2026-004",
        "amount": 1400.0,
        "reason": "CANCELLATION",
        "status": "PENDING",
        "source": "ADMIN_MANUAL",
        "notes": "Admin-initiated refund for late cancellation policy exception.",
        "assigneeId": None,
    },
    {
        "patient_email": "patient@test.com",
        "booking_id": "BK-2026-005",
        "amount": 2200.0,
        "reason": "DOUBLE_CHARGE",
        "status": "APPROVED",
        "source": "ADMIN_MANUAL",
        "notes": "Verified double charge on equipment rental. Full refund approved.",
        "resolved_days_ago": 1,
    },
    {
        "patient_email": "ramesh@test.com",
        "booking_id": "BK-2026-006",
        "amount": 500.0,
        "reason": "NO_SHOW",
        "status": "DENIED",
        "source": "THERAPIST_SUBMITTED",
        "denyReason": "GPS check-in confirmed therapist arrived. Patient was not available.",
        "notes": "Therapist submitted dispute after patient claimed no-show.",
        "resolved_days_ago": 7,
    },
    {
        "patient_email": "sita@test.com",
        "booking_id": "BK-2026-007",
        "amount": 1000.0,
        "reason": "CANCELLATION",
        "status": "PENDING",
        "source": "PATIENT_SUBMITTED",
        "notes": "Patient cancelled within the 2-hour window but was still charged.",
    },
]


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    created = 0
    skipped = 0

    for r in REFUNDS:
        patient = await db.user.find_unique(where={"email": r["patient_email"]})
        if not patient:
            print(f"SKIP refund — patient not found ({r['patient_email']})")
            skipped += 1
            continue

        existing = await db.refund.find_first(
            where={"bookingId": r["booking_id"]}
        )
        if existing:
            print(f"SKIP refund — booking {r['booking_id']} already has a refund")
            skipped += 1
            continue

        now = datetime.now(timezone.utc)
        file_days_ago = r.get("resolved_days_ago", 10) + 2
        created_at = now - timedelta(days=file_days_ago)
        resolved_at = None
        if r["status"] in ("APPROVED", "DENIED") and r.get("resolved_days_ago"):
            resolved_at = created_at + timedelta(days=r["resolved_days_ago"] - 1)

        refund = await db.refund.create(
            data={
                "patientId": patient.id,
                "bookingId": r["booking_id"],
                "amount": r["amount"],
                "reason": r["reason"],
                "status": r["status"],
                "source": r["source"],
                "notes": r.get("notes"),
                "denyReason": r.get("denyReason"),
                "createdAt": created_at,
                "resolvedAt": resolved_at,
            }
        )
        print(f"CREATED refund — {r['booking_id']} ({r['reason']}, {r['status']}) id={refund.id}")
        created += 1

    await db.disconnect()
    print(f"\nRefunds seeded: {created} created, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(main())
