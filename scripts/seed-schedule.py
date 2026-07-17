"""
Seed script for therapist schedule view.
Creates sessions for therapist@test.com across July 2026 with varied statuses.
Run: python scripts/seed-schedule.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

THERAPIST_EMAIL = "therapist@test.com"

SESSIONS = [
    # ── Past sessions (completed) ─────────────────
    {"patient_email": "patient@test.com",  "date": datetime(2026, 7, 1),  "time": "09:00", "type": "HOME_VISIT", "status": "COMPLETED",  "address": "Thamel, Kathmandu",       "fee": 1500},
    {"patient_email": "ramesh@test.com",   "date": datetime(2026, 7, 2),  "time": "11:00", "type": "HOME_VISIT", "status": "COMPLETED",  "address": "Baluwatar, Kathmandu",     "fee": 1500},
    {"patient_email": "sita@test.com",     "date": datetime(2026, 7, 3),  "time": "14:00", "type": "CLINIC",     "status": "COMPLETED",  "address": "Jhamsikhel, Lalitpur",     "fee": 1500},
    {"patient_email": "hari@test.com",     "date": datetime(2026, 7, 4),  "time": "10:00", "type": "HOME_VISIT", "status": "COMPLETED",  "address": "Bhaktapur Durbar Sq.",     "fee": 1500},
    {"patient_email": "patient@test.com",  "date": datetime(2026, 7, 5),  "time": "16:00", "type": "HOME_VISIT", "status": "COMPLETED",  "address": "Thamel, Kathmandu",       "fee": 1500},
    {"patient_email": "ramesh@test.com",   "date": datetime(2026, 7, 7),  "time": "09:00", "type": "HOME_VISIT", "status": "COMPLETED",  "address": "Baluwatar, Kathmandu",     "fee": 1500},
    {"patient_email": "sita@test.com",     "date": datetime(2026, 7, 8),  "time": "14:00", "type": "CLINIC",     "status": "COMPLETED",  "address": "Jhamsikhel, Lalitpur",     "fee": 1500},
    {"patient_email": "hari@test.com",     "date": datetime(2026, 7, 10), "time": "10:00", "type": "HOME_VISIT", "status": "COMPLETED",  "address": "Bhaktapur",                "fee": 1500},
    {"patient_email": "patient@test.com",  "date": datetime(2026, 7, 11), "time": "11:00", "type": "HOME_VISIT", "status": "COMPLETED",  "address": "Thamel, Kathmandu",       "fee": 1500},
    {"patient_email": "ramesh@test.com",   "date": datetime(2026, 7, 14), "time": "09:00", "type": "HOME_VISIT", "status": "COMPLETED",  "address": "Baluwatar, Kathmandu",     "fee": 1500},

    # ── Past session (cancelled) ─────────────────
    {"patient_email": "sita@test.com",     "date": datetime(2026, 7, 9),  "time": "14:00", "type": "CLINIC",     "status": "CANCELLED",  "address": "Jhamsikhel, Lalitpur",     "fee": 1500},

    # ── Today (July 17) ─────────────────────────
    {"patient_email": "patient@test.com",  "date": datetime(2026, 7, 17), "time": "08:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Budhanilkantha, Kathmandu","fee": 1500},
    {"patient_email": "ramesh@test.com",   "date": datetime(2026, 7, 17), "time": "10:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Baluwatar, Kathmandu",     "fee": 1500},
    {"patient_email": "hari@test.com",     "date": datetime(2026, 7, 17), "time": "14:00", "type": "CLINIC",     "status": "IN_PROGRESS","address": "Bhaktapur",                "fee": 1500},

    # ── This week (July 18–20) ──────────────────
    {"patient_email": "sita@test.com",     "date": datetime(2026, 7, 18), "time": "09:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Jhamsikhel, Lalitpur",     "fee": 1500},
    {"patient_email": "patient@test.com",  "date": datetime(2026, 7, 18), "time": "14:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Thamel, Kathmandu",       "fee": 1500},
    {"patient_email": "ramesh@test.com",   "date": datetime(2026, 7, 19), "time": "10:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Baluwatar, Kathmandu",     "fee": 1500},
    {"patient_email": "hari@test.com",     "date": datetime(2026, 7, 20), "time": "16:00", "type": "CLINIC",     "status": "SCHEDULED",  "address": "Bhaktapur",                "fee": 1500},

    # ── Next week (July 21–27) ──────────────────
    {"patient_email": "sita@test.com",     "date": datetime(2026, 7, 21), "time": "09:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Jhamsikhel, Lalitpur",     "fee": 1500},
    {"patient_email": "patient@test.com",  "date": datetime(2026, 7, 21), "time": "14:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Thamel, Kathmandu",       "fee": 1500},
    {"patient_email": "ramesh@test.com",   "date": datetime(2026, 7, 22), "time": "11:00", "type": "HOME_VISIT", "status": "RESCHEDULE_REQUESTED", "address": "Baluwatar, Kathmandu", "fee": 1500,
     "notes": "Traffic delay from prior home visit — proposed 3:00 PM instead.|"},
    {"patient_email": "hari@test.com",     "date": datetime(2026, 7, 22), "time": "16:00", "type": "CLINIC",     "status": "SCHEDULED",  "address": "Bhaktapur",                "fee": 1500},
    {"patient_email": "sita@test.com",     "date": datetime(2026, 7, 23), "time": "10:00", "type": "HOME_VISIT", "status": "DECLINE_REQUESTED",   "address": "Jhamsikhel, Lalitpur", "fee": 1500,
     "notes": "Double-booked with a home visit that overran — requesting cancellation, patient to rebook.|"},
    {"patient_email": "patient@test.com",  "date": datetime(2026, 7, 24), "time": "09:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Sanepa, Lalitpur",        "fee": 1500},
    {"patient_email": "ramesh@test.com",   "date": datetime(2026, 7, 25), "time": "14:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Gatthaghar, Bhaktapur",    "fee": 1500},
    {"patient_email": "hari@test.com",     "date": datetime(2026, 7, 26), "time": "09:00", "type": "CLINIC",     "status": "SCHEDULED",  "address": "Bhaktapur",                "fee": 1500},
    {"patient_email": "sita@test.com",     "date": datetime(2026, 7, 27), "time": "11:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Mangal Bazaar, Lalitpur",  "fee": 1500},

    # ── Week after (July 28–31) ─────────────────
    {"patient_email": "patient@test.com",  "date": datetime(2026, 7, 28), "time": "10:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Thankot, Kathmandu",       "fee": 1500},
    {"patient_email": "ramesh@test.com",   "date": datetime(2026, 7, 29), "time": "09:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Balkhu, Kathmandu",        "fee": 1500},
    {"patient_email": "hari@test.com",     "date": datetime(2026, 7, 30), "time": "14:00", "type": "CLINIC",     "status": "SCHEDULED",  "address": "Kalanki, Kathmandu",       "fee": 1500},
    {"patient_email": "sita@test.com",     "date": datetime(2026, 7, 31), "time": "11:00", "type": "HOME_VISIT", "status": "SCHEDULED",  "address": "Imadole, Lalitpur",        "fee": 1500},
]


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    therapist_user = await db.user.find_unique(where={"email": THERAPIST_EMAIL})
    if not therapist_user:
        print(f"ERROR — therapist user not found ({THERAPIST_EMAIL})")
        await db.disconnect()
        return

    therapist = await db.therapist.find_unique(where={"userId": therapist_user.id})
    if not therapist:
        print(f"ERROR — therapist profile not found for {THERAPIST_EMAIL}")
        await db.disconnect()
        return

    created = skipped = 0
    for s in SESSIONS:
        patient = await db.user.find_unique(where={"email": s["patient_email"]})
        if not patient:
            print(f"SKIP — patient not found ({s['patient_email']})")
            skipped += 1
            continue

        existing = await db.session.find_first(
            where={
                "therapistId": therapist.id,
                "patientId": patient.id,
                "date": s["date"],
                "time": s["time"],
            }
        )
        if existing:
            print(f"SKIP — {s['patient_email']} @ {s['date'].date()} {s['time']} (exists)")
            skipped += 1
            continue

        await db.session.create(
            data={
                "therapistId": therapist.id,
                "patientId": patient.id,
                "date": s["date"],
                "time": s["time"],
                "type": s["type"],
                "status": s["status"],
                "address": s["address"],
                "fee": s["fee"],
                "notes": s.get("notes"),
            }
        )
        print(f"CREATED — {s['patient_email']} @ {s['date'].date()} {s['time']} [{s['status']}]")
        created += 1

    await db.disconnect()
    print(f"\nDone. Created: {created}, Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(main())
