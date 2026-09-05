"""
Seed admin-facing data for the dynamic admin pages:
   1. Service Areas (with assigned therapists)          -> /admin/service-areas + /admin/analytics/bookings-by-zone
   2. Complaints (as safety incidents)                   -> /admin/incidents + /admin/complaints
   3. Extra ADMIN users (team)                           -> /admin/team
   4. COMPLETED payments spread over months              -> /admin/analytics/revenue-trend
   5. Therapist document verifications                   -> /admin/verifications

Idempotent: skips records that already exist.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Json, Prisma
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SERVICE_AREAS = [
    {
        "name": "Kathmandu Central",
        "localities": ["Baneshwor", "New Baneshwor", "Koteshwor", "Baluwatar"],
        "therapists": ["Dr. Jane Smith", "Dr. Bibek Thapa", "Dr. Sushmita Rai"],
    },
    {
        "name": "Lalitpur / Patan",
        "localities": ["Patan", "Jawalakhel", "Sanepa", "Kupondole"],
        "therapists": ["Dr. Aarati Shrestha", "Dr. Sabina Gurung"],
    },
    {
        "name": "Gongabu & Boudha",
        "localities": ["Gongabu", "Boudha", "Jorpati", "Tokha"],
        "therapists": ["Dr. Nirajan Karki"],
    },
    {
        "name": "Bhaktapur",
        "localities": ["Bhaktapur Durbar Area", "Suryabinayak", "Kamalbinayak"],
        "therapists": [],
    },
]

COMPLAINTS = [
    {
        "type": "patient",
        "therapist": "Dr. Jane Smith",
        "patient": "Hari Pradhan",
        "category": "Safety",
        "priority": "Urgent",
        "status": "Open",
        "days_ago": 0,
        "description": "Patient reports feeling unsafe, therapist behaving inappropriately mid-session",
    },
    {
        "type": "therapist",
        "therapist": "Dr. Aarati Shrestha",
        "patient": "Sita Lama",
        "category": "Conduct",
        "priority": "Normal",
        "status": "In Progress",
        "days_ago": 1,
        "description": "Aggressive family member present at home during session",
    },
    {
        "type": "patient",
        "therapist": "Dr. Bibek Thapa",
        "patient": "Ramesh Adhikari",
        "category": "Service Quality",
        "priority": "High",
        "status": "Open",
        "days_ago": 2,
        "description": "Therapist arrived 40 minutes late without prior notice",
    },
    {
        "type": "patient",
        "therapist": "Dr. Nirajan Karki",
        "patient": "John Doe",
        "category": "Conduct",
        "priority": "High",
        "status": "Escalated",
        "days_ago": 3,
        "description": "Therapist left session early without explanation",
    },
    {
        "type": "therapist",
        "therapist": "Dr. Rajan Magar",
        "patient": "Sita Lama",
        "category": "Conduct",
        "priority": "Normal",
        "status": "Resolved",
        "days_ago": 5,
        "description": "Patient cancelled at the door after session confirmed",
    },
    {
        "type": "patient",
        "therapist": "Dr. Sabina Gurung",
        "patient": "Hari Pradhan",
        "category": "Billing",
        "priority": "High",
        "status": "Resolved",
        "days_ago": 7,
        "description": "Charged for a session that was rescheduled due to therapist unavailability",
    },
]

ADMIN_USERS = [
    {"name": "Roshani Sharma", "email": "roshani@sahayatriphysio.com", "city": "Kathmandu"},
    {"name": "Bikash Karki", "email": "bikash@sahayatriphysio.com", "city": "Lalitpur"},
]

# (month_offset from now, amount, method) — revenue trend
PAYMENTS = [
    (5, 145000, "ESHOPPOS"),
    (5, 25000, "CASH"),
    (4, 168000, "ESHOPPOS"),
    (4, 22000, "CASH"),
    (3, 181000, "ESHOPPOS"),
    (3, 30000, "CASH"),
    (2, 204000, "ESHOPPOS"),
    (2, 18000, "CASH"),
    (1, 218000, "ESHOPPOS"),
    (1, 35000, "CASH"),
    (0, 124000, "ESHOPPOS"),
    (0, 42000, "CASH"),
]

# (therapist name, documentType, status, expires_in_days | None, severity, reportedBy)
VERIFICATIONS = [
    ("Dr. Bibek Thapa", "Practice license", "Pending review", 760, "High", "System"),
    ("Dr. Aarati Shrestha", "Government ID", "Pending review", None, "Low", "Admin"),
    ("Dr. Nirajan Karki", "Certification", "Pending review", 340, "Medium", "System"),
    ("Dr. Sabina Gurung", "Practice license", "Verified", 900, "Low", "Admin"),
    ("Dr. Rajan Magar", "Government ID", "Verified", 150, "Low", "Admin"),
    ("Dr. Anil Shakya", "Certification", "Expiring soon", 40, "Critical", "System"),
    ("Dr. Sushmita Rai", "Practice license", "Expired", -20, "Critical", "System"),
]


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    now = datetime.now(timezone.utc)

    # ---- 1. Service Areas ----
    created_areas = skipped_areas = 0
    for area in SERVICE_AREAS:
        existing = await db.servicearea.find_first(where={"name": area["name"]})
        if existing:
            skipped_areas += 1
            print(f"SKIP service area — {area['name']} exists")
            continue

        obj = await db.servicearea.create(
            data={
                "name": area["name"],
                "localities": Json(area["localities"]),
                "status": "Active" if area["therapists"] else "Low coverage",
            }
        )

        for therapist_name in area["therapists"]:
            therapist = await db.therapist.find_first(where={"name": therapist_name})
            if therapist:
                await db.therapistservicearea.create(
                    data={"therapistId": therapist.id, "serviceAreaId": obj.id}
                )
        created_areas += 1
        print(f"CREATED service area — {area['name']} (id={obj.id})")

    print(f"Service areas: {created_areas} created, {skipped_areas} skipped")

    # ---- 2. Complaints (incidents) ----
    created_c = skipped_c = 0
    for c in COMPLAINTS:
        therapist = await db.therapist.find_first(where={"name": c["therapist"]})
        patient = await db.user.find_first(where={"name": c["patient"]})
        if not therapist or not patient:
            print(f"SKIP complaint — missing therapist/patient ({c['therapist']}/{c['patient']})")
            skipped_c += 1
            continue

        complainant_id = patient.id if c["type"] == "patient" else therapist.id
        against_id = therapist.id if c["type"] == "patient" else patient.id

        duplicate = await db.complaint.find_first(
            where={
                "complainantId": complainant_id,
                "againstId": against_id,
                "description": c["description"],
            }
        )
        if duplicate:
            skipped_c += 1
            print(f"SKIP complaint — duplicate ({c['description'][:40]}...)")
            continue

        complaint = await db.complaint.create(
            data={
                "type": c["type"],
                "complainantName": patient.name if c["type"] == "patient" else therapist.name,
                "againstName": therapist.name if c["type"] == "patient" else patient.name,
                "complainantId": complainant_id,
                "againstId": against_id,
                "category": c["category"],
                "priority": c["priority"],
                "status": c["status"],
                "description": c["description"],
                "createdAt": now - timedelta(days=c["days_ago"], hours=3),
                "source": "PATIENT_SUBMITTED" if c["type"] == "patient" else "THERAPIST_SUBMITTED",
            }
        )
        created_c += 1
        print(f"CREATED complaint/incident — {c['description'][:40]}... (status={c['status']}) id={complaint.id}")

    print(f"Complaints/incidents: {created_c} created, {skipped_c} skipped")

    # ---- 3. Therapist document verifications ----
    created_v = skipped_v = 0
    for (therapist_name, doc_type, status, expires_in_days, severity, reported_by) in VERIFICATIONS:
        therapist = await db.therapist.find_first(where={"name": therapist_name})
        if not therapist:
            print(f"SKIP verification — therapist not found: {therapist_name}")
            skipped_v += 1
            continue
        duplicate = await db.verification.find_first(
            where={"therapistId": therapist.id, "documentType": doc_type}
        )
        if duplicate:
            skipped_v += 1
            print(f"SKIP verification — {therapist_name} / {doc_type} exists")
            continue

        expires = None
        if expires_in_days is not None:
            expires = now + timedelta(days=expires_in_days)
        await db.verification.create(
            data={
                "therapistId": therapist.id,
                "documentType": doc_type,
                "documentUrl": f"/api/v1/uploads/therapists/{therapist.id}/documents/sample.pdf",
                "fileName": f"{doc_type.replace(' ', '-').lower()}.pdf",
                "fileSize": 204800,
                "uploaded": now - timedelta(days=45),
                "expires": expires,
                "status": status,
                "severity": severity,
                "reportedBy": reported_by,
            }
        )
        created_v += 1
        print(f"CREATED verification — {therapist_name} / {doc_type} ({status})")

    print(f"Verifications: {created_v} created, {skipped_v} skipped")

    # ---- 5. Admin users (team) ----
    created_u = skipped_u = 0
    for u in ADMIN_USERS:
        existing = await db.user.find_unique(where={"email": u["email"]})
        if existing:
            skipped_u += 1
            print(f"SKIP admin user — {u['email']} exists")
            continue

        await db.user.create(
            data={
                "name": u["name"],
                "email": u["email"],
                "password": _pwd_context.hash("password123"),
                "role": "ADMIN",
                "status": "APPROVED",
                "city": u["city"],
            }
        )
        created_u += 1
        print(f"CREATED admin user — {u['name']} ({u['email']})")

    print(f"Admin users: {created_u} created, {skipped_u} skipped")

    # ---- 6. Payments (revenue trend) ----
    created_p = skipped_p = 0
    patients = await db.user.find_many(where={"role": "PATIENT"})
    for i, (month_off, amount, method) in enumerate(PAYMENTS):
        if not patients:
            break
        patient = patients[i % len(patients)]
        if month_off == 0:
            created_at = (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        else:
            created_at = (now - timedelta(days=30 * month_off)).replace(hour=12, minute=0, second=0, microsecond=0)

        duplicate = await db.payment.find_first(
            where={"amount": amount, "createdAt": {"gte": created_at, "lt": created_at + timedelta(days=1)}}
        )
        if duplicate:
            skipped_p += 1
            continue

        await db.payment.create(
            data={
                "userId": patient.id,
                "amount": float(amount),
                "status": "COMPLETED",
                "method": method,
                "currency": "NPR",
                "paymentType": "SESSION",
                "createdAt": created_at,
            }
        )
        created_p += 1
        print(f"CREATED payment — Rs {amount:,.0f} ({created_at.strftime('%Y-%m')})")

    print(f"Payments: {created_p} created, {skipped_p} skipped")

    await db.disconnect()
    print("\nAdmin data seeding complete.")


if __name__ == "__main__":
    asyncio.run(main())