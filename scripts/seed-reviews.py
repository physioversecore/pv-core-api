import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    patient = await db.user.find_unique(where={"email": "patient@test.com"})
    if not patient:
        print("SKIP reviews — patient@test.com not found")
        return

    sessions = await db.session.find_many(
        where={"patientId": patient.id, "status": "COMPLETED"},
        include={"therapist": True},
        order={"date": "asc"},
    )

    # Leave the 3 most recent completed sessions unrated
    rated_sessions = sessions[:-3] if len(sessions) > 3 else []

    for s in rated_sessions:
        existing = await db.review.find_unique(where={"sessionId": s.id})
        if existing:
            print(f"SKIP review — session {s.id} already reviewed")
            continue

        await db.review.create(
            data={
                "sessionId": s.id,
                "patientId": patient.id,
                "therapistId": s.therapistId,
                "rating": 5,
                "comment": "Great session! Very helpful.",
            }
        )
        print(f"CREATED review — session {s.id} (therapist {s.therapist.name})")

    print(f"\nReviews seeded ({len(rated_sessions)} created).")
    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
