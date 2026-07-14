import asyncio
import secrets
import string
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma


def _make_referral_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "SAHA-" + "".join(secrets.choice(chars) for _ in range(8))


TODAY_SESSIONS = [
    {
        "therapist_email": "therapist@test.com",
        "patient_email": "patient@test.com",
        "time": "10:00",
        "type": "HOME_VISIT",
        "status": "SCHEDULED",
        "address": "Thamel, Kathmandu",
        "fee": 1500,
    },
    {
        "therapist_email": "therapist@test.com",
        "patient_email": "ramesh@test.com",
        "time": "14:00",
        "type": "HOME_VISIT",
        "status": "SCHEDULED",
        "address": "Baluwatar, Kathmandu",
        "fee": 1500,
    },
    {
        "therapist_email": "therapist@test.com",
        "patient_email": "sita@test.com",
        "time": "17:00",
        "type": "CLINIC",
        "status": "IN_PROGRESS",
        "address": "Jhamsikhel, Lalitpur",
        "fee": 1500,
    },
]

WEEK_SESSIONS = [
    {
        "therapist_email": "therapist@test.com",
        "patient_email": "hari@test.com",
        "day_offset": -1,
        "time": "09:00",
        "type": "HOME_VISIT",
        "status": "COMPLETED",
        "address": "Bhaktapur",
        "fee": 1500,
    },
    {
        "therapist_email": "therapist@test.com",
        "patient_email": "patient@test.com",
        "day_offset": -2,
        "time": "11:00",
        "type": "HOME_VISIT",
        "status": "COMPLETED",
        "address": "Thamel, Kathmandu",
        "fee": 1500,
    },
    {
        "therapist_email": "therapist@test.com",
        "patient_email": "ramesh@test.com",
        "day_offset": -3,
        "time": "15:00",
        "type": "HOME_VISIT",
        "status": "COMPLETED",
        "address": "Baluwatar, Kathmandu",
        "fee": 1500,
    },
]

REPORTS = [
    {
        "therapist_email": "therapist@test.com",
        "patient_email": "patient@test.com",
        "title": "Session note — Knee rehab week 6",
        "content": "Range of motion improving. Patient can now flex knee to 110°. Continue with quad sets and hamstring stretches.",
        "file_url": "https://storage.sahayatri.np/reports/knee-xray-02jun.pdf",
    },
    {
        "therapist_email": "therapist@test.com",
        "patient_email": "ramesh@test.com",
        "title": "Progress report — Lower back",
        "content": "Posture exercises showing improvement. Lumbar flexibility increased by 15 degrees since last session.",
        "file_url": None,
    },
    {
        "therapist_email": "therapist@test.com",
        "patient_email": "sita@test.com",
        "title": "Exercise video — Quad strengthening",
        "content": "Demonstrated quad strengthening exercises for post-ACL recovery. Patient performed well.",
        "file_url": "https://storage.sahayatri.np/reports/quad-exercise-demo.mp4",
    },
]

REVIEWS = [
    {
        "therapist_email": "therapist@test.com",
        "patient_email": "patient@test.com",
        "rating": 5,
        "comment": "Very professional and patient. Exercises helped a lot with my recovery.",
    },
    {
        "therapist_email": "therapist@test.com",
        "patient_email": "ramesh@test.com",
        "rating": 5,
        "comment": "Always on time and explains everything clearly. Highly recommended!",
    },
]


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for s in TODAY_SESSIONS:
        therapist_user = await db.user.find_unique(where={"email": s["therapist_email"]})
        if not therapist_user:
            print(f"SKIP — therapist user not found ({s['therapist_email']})")
            continue
        therapist = await db.therapist.find_unique(where={"userId": therapist_user.id})
        if not therapist:
            print(f"SKIP — therapist profile not found for {s['therapist_email']}")
            continue
        patient = await db.user.find_unique(where={"email": s["patient_email"]})
        if not patient:
            print(f"SKIP — patient not found ({s['patient_email']})")
            continue

        existing = await db.session.find_first(
            where={
                "therapistId": therapist.id,
                "patientId": patient.id,
                "date": today,
                "time": s["time"],
            }
        )
        if existing:
            print(f"SKIP today session — {s['patient_email']} @ {s['time']} (exists)")
            continue

        await db.session.create(
            data={
                "therapistId": therapist.id,
                "patientId": patient.id,
                "date": today,
                "time": s["time"],
                "type": s["type"],
                "status": s["status"],
                "address": s["address"],
                "fee": s["fee"],
            }
        )
        print(f"CREATED today session — {s['patient_email']} @ {s['time']}")

    for s in WEEK_SESSIONS:
        therapist_user = await db.user.find_unique(where={"email": s["therapist_email"]})
        if not therapist_user:
            continue
        therapist = await db.therapist.find_unique(where={"userId": therapist_user.id})
        if not therapist:
            continue
        patient = await db.user.find_unique(where={"email": s["patient_email"]})
        if not patient:
            continue

        session_date = today + timedelta(days=s["day_offset"])
        existing = await db.session.find_first(
            where={
                "therapistId": therapist.id,
                "patientId": patient.id,
                "date": session_date,
                "time": s["time"],
            }
        )
        if existing:
            print(f"SKIP week session — {s['patient_email']} @ {session_date.date()} (exists)")
            continue

        await db.session.create(
            data={
                "therapistId": therapist.id,
                "patientId": patient.id,
                "date": session_date,
                "time": s["time"],
                "type": s["type"],
                "status": s["status"],
                "address": s["address"],
                "fee": s["fee"],
            }
        )
        print(f"CREATED week session — {s['patient_email']} @ {session_date.date()}")

    for r in REPORTS:
        patient = await db.user.find_unique(where={"email": r["patient_email"]})
        if not patient:
            print(f"SKIP report — patient not found ({r['patient_email']})")
            continue

        existing = await db.report.find_first(
            where={"patientId": patient.id, "title": r["title"]}
        )
        if existing:
            print(f"SKIP report — '{r['title']}' (exists)")
            continue

        data = {
            "patientId": patient.id,
            "title": r["title"],
            "content": r["content"],
        }
        if r.get("file_url"):
            data["fileUrl"] = r["file_url"]

        await db.report.create(data=data)
        print(f"CREATED report — '{r['title']}'")

    for rv in REVIEWS:
        patient = await db.user.find_unique(where={"email": rv["patient_email"]})
        if not patient:
            continue

        existing_review = await db.review.find_first(
            where={"patientId": patient.id}
        )
        if existing_review:
            print(f"SKIP review — patient {rv['patient_email']} already has a review")
            continue

        session = await db.session.find_first(
            where={
                "patientId": patient.id,
                "status": "COMPLETED",
            },
            order={"date": "desc"},
        )
        if not session:
            print(f"SKIP review — no completed session for {rv['patient_email']}")
            continue

        existing = await db.review.find_unique(where={"sessionId": session.id})
        if existing:
            print(f"SKIP review — session {session.id} already reviewed")
            continue

        await db.review.create(
            data={
                "sessionId": session.id,
                "patientId": patient.id,
                "therapistId": session.therapistId,
                "rating": rv["rating"],
                "comment": rv["comment"],
            }
        )
        print(f"CREATED review — {rv['patient_email']} for session {session.id}")

    therapist_user = await db.user.find_unique(where={"email": "therapist@test.com"})
    if therapist_user and not therapist_user.referralCode:
        code = _make_referral_code()
        await db.user.update(where={"id": therapist_user.id}, data={"referralCode": code})
        print(f"CREATED referral code for therapist@test.com: {code}")

    await db.disconnect()
    print("\nTherapist dashboard data seeded.")


if __name__ == "__main__":
    asyncio.run(main())
