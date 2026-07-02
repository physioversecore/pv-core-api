from prisma import Prisma


async def create_report(db: Prisma, data: dict):
    return await db.report.create(data=data)


async def get_reports_for_patient(db: Prisma, patient_id: str, skip=0, limit=100):
    reports = await db.report.find_many(
        where={"patientId": patient_id},
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
    )
    total = await db.report.count(where={"patientId": patient_id})
    return reports, total


async def get_report(db: Prisma, report_id: str):
    return await db.report.find_unique(where={"id": report_id})


async def update_report(db: Prisma, report_id: str, data: dict):
    return await db.report.update(where={"id": report_id}, data=data)


async def delete_report(db: Prisma, report_id: str):
    await db.report.delete(where={"id": report_id})
