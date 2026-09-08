from datetime import datetime, timedelta, timezone

from prisma import Prisma


async def purchase_package(
    db: Prisma,
    user_id: str,
    package_id: str,
    payment_method: str = "CASH",
) -> dict:
    package = await db.package.find_unique(where={"id": package_id})
    if not package:
        raise ValueError("Package not found")
    if not package.isActive:
        raise ValueError("Package is no longer available")

    existing_active = await db.packagepurchase.find_first(
        where={"userId": user_id, "status": "ACTIVE"}
    )
    if existing_active:
        raise ValueError("You already have an active package. Use your remaining sessions first.")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=package.validityDays)

    payment = await db.payment.create(
        data={
            "userId": user_id,
            "amount": float(package.price),
            "status": "COMPLETED",
            "method": payment_method.upper(),
            "currency": "NPR",
            "platformFee": 0,
            "paymentType": "PACKAGE",
        }
    )

    purchase = await db.packagepurchase.create(
        data={
            "userId": user_id,
            "packageId": package_id,
            "paymentId": payment.id,
            "sessionsTotal": package.sessionCount,
            "sessionsUsed": 0,
            "status": "ACTIVE",
            "purchasedAt": now,
            "expiresAt": expires_at,
        }
    )

    return {
        "id": purchase.id,
        "userId": purchase.userId,
        "packageId": purchase.packageId,
        "packageName": package.name,
        "packageTag": package.tag,
        "sessionsTotal": purchase.sessionsTotal,
        "sessionsUsed": purchase.sessionsUsed,
        "sessionsRemaining": purchase.sessionsTotal - purchase.sessionsUsed,
        "status": purchase.status,
        "purchasedAt": purchase.purchasedAt.isoformat() if purchase.purchasedAt else "",
        "expiresAt": purchase.expiresAt.isoformat() if purchase.expiresAt else "",
        "createdAt": purchase.createdAt.isoformat() if purchase.createdAt else "",
        "updatedAt": purchase.updatedAt.isoformat() if purchase.updatedAt else "",
        "validityDays": package.validityDays or 0,
        "amount": float(package.price or 0),
        "payment": {
            "id": payment.id,
            "amount": payment.amount,
            "method": payment.method,
            "status": payment.status,
        },
    }


async def get_user_purchases(
    db: Prisma,
    user_id: str,
    status: str | None = None,
) -> list[dict]:
    where: dict = {"userId": user_id}
    if status:
        where["status"] = status

    purchases = await db.packagepurchase.find_many(
        where=where,
        order={"createdAt": "desc"},
    )

    results = []
    for p in purchases:
        package = await db.package.find_unique(where={"id": p.packageId})
        results.append({
            "id": p.id,
            "userId": p.userId,
            "packageId": p.packageId,
            "packageName": package.name if package else "Unknown",
            "packageTag": package.tag if package else "",
            "sessionsTotal": p.sessionsTotal,
            "sessionsUsed": p.sessionsUsed,
            "sessionsRemaining": p.sessionsTotal - p.sessionsUsed,
            "status": p.status,
            "purchasedAt": p.purchasedAt.isoformat() if p.purchasedAt else "",
            "expiresAt": p.expiresAt.isoformat() if p.expiresAt else "",
            "createdAt": p.createdAt.isoformat() if p.createdAt else "",
            "updatedAt": p.updatedAt.isoformat() if p.updatedAt else "",
        })

    return results


async def get_active_purchase(db: Prisma, user_id: str) -> dict | None:
    now = datetime.now(timezone.utc)

    purchase = await db.packagepurchase.find_first(
        where={
            "userId": user_id,
            "status": "ACTIVE",
        },
        order={"expiresAt": "asc"},
    )

    if not purchase:
        return None

    if purchase.expiresAt and purchase.expiresAt < now:
        await db.packagepurchase.update(
            where={"id": purchase.id},
            data={"status": "EXPIRED"},
        )
        return None

    if purchase.sessionsUsed >= purchase.sessionsTotal:
        await db.packagepurchase.update(
            where={"id": purchase.id},
            data={"status": "DEPLETED"},
        )
        return None

    package = await db.package.find_unique(where={"id": purchase.packageId})

    sessions = await db.session.find_many(
        where={"packagePurchaseId": purchase.id},
        include={"therapist": True},
        order={"date": "desc"},
    )

    session_list = []
    for s in sessions:
        session_list.append({
            "id": s.id,
            "date": s.date.strftime("%Y-%m-%d") if s.date else "",
            "time": s.time or "",
            "therapistName": s.therapist.name if s.therapist else "",
            "status": s.status,
        })

    return {
        "id": purchase.id,
        "userId": purchase.userId,
        "packageId": purchase.packageId,
        "packageName": package.name if package else "Unknown",
        "packageTag": package.tag if package else "",
        "sessionsTotal": purchase.sessionsTotal,
        "sessionsUsed": purchase.sessionsUsed,
        "sessionsRemaining": purchase.sessionsTotal - purchase.sessionsUsed,
        "status": purchase.status,
        "purchasedAt": purchase.purchasedAt.isoformat() if purchase.purchasedAt else "",
        "expiresAt": purchase.expiresAt.isoformat() if purchase.expiresAt else "",
        "createdAt": purchase.createdAt.isoformat() if purchase.createdAt else "",
        "updatedAt": purchase.updatedAt.isoformat() if purchase.updatedAt else "",
        "sessions": session_list,
    }


async def deduct_session(db: Prisma, package_purchase_id: str) -> dict:
    purchase = await db.packagepurchase.find_unique(where={"id": package_purchase_id})
    if not purchase:
        raise ValueError("Package purchase not found")

    new_used = purchase.sessionsUsed + 1
    new_status = "DEPLETED" if new_used >= purchase.sessionsTotal else "ACTIVE"

    updated = await db.packagepurchase.update(
        where={"id": package_purchase_id},
        data={"sessionsUsed": new_used, "status": new_status},
    )

    return {
        "id": updated.id,
        "sessionsUsed": updated.sessionsUsed,
        "sessionsRemaining": updated.sessionsTotal - updated.sessionsUsed,
        "status": updated.status,
    }


async def restore_session(db: Prisma, package_purchase_id: str) -> dict:
    purchase = await db.packagepurchase.find_unique(where={"id": package_purchase_id})
    if not purchase:
        raise ValueError("Package purchase not found")

    new_used = max(0, purchase.sessionsUsed - 1)
    new_status = "ACTIVE"

    updated = await db.packagepurchase.update(
        where={"id": package_purchase_id},
        data={"sessionsUsed": new_used, "status": new_status},
    )

    return {
        "id": updated.id,
        "sessionsUsed": updated.sessionsUsed,
        "sessionsRemaining": updated.sessionsTotal - updated.sessionsUsed,
        "status": updated.status,
    }


async def check_and_expire_purchases(db: Prisma) -> int:
    now = datetime.now(timezone.utc)
    result = await db.packagepurchase.update_many(
        where={
            "status": "ACTIVE",
            "expiresAt": {"lt": now},
        },
        data={"status": "EXPIRED"},
    )
    return result.count


async def get_admin_package_purchases(
    db: Prisma,
    *,
    skip: int = 0,
    limit: int = 10,
    status: str | None = None,
    package_id: str | None = None,
) -> tuple[list[dict], int]:
    where: dict = {}
    if status:
        where["status"] = status
    if package_id:
        where["packageId"] = package_id

    total = await db.packagepurchase.count(where=where)

    purchases = await db.packagepurchase.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
    )

    items = []
    for p in purchases:
        user = await db.user.find_unique(where={"id": p.userId})
        package = await db.package.find_unique(where={"id": p.packageId})
        items.append({
            "id": p.id,
            "patientName": user.name if user else "Unknown",
            "patientId": p.userId,
            "packageName": package.name if package else "Unknown",
            "packageId": p.packageId,
            "sessionsTotal": p.sessionsTotal,
            "sessionsUsed": p.sessionsUsed,
            "sessionsRemaining": p.sessionsTotal - p.sessionsUsed,
            "status": p.status,
            "amount": float(package.price) if package else 0,
            "purchasedAt": p.purchasedAt.strftime("%Y-%m-%d") if p.purchasedAt else "",
            "expiresAt": p.expiresAt.strftime("%Y-%m-%d") if p.expiresAt else "",
        })

    return items, total


async def get_admin_package_stats(db: Prisma) -> dict:
    total_purchases = await db.packagepurchase.count()
    active_purchases = await db.packagepurchase.count(where={"status": "ACTIVE"})

    all_purchases = await db.packagepurchase.find_many()
    total_revenue = 0.0
    sessions_delivered = 0
    package_counts: dict[str, int] = {}

    for p in all_purchases:
        sessions_delivered += p.sessionsUsed
        package = await db.package.find_unique(where={"id": p.packageId})
        if package:
            total_revenue += float(package.price)
            package_counts[package.name] = package_counts.get(package.name, 0) + 1

    most_popular = max(package_counts, key=package_counts.get) if package_counts else None

    return {
        "totalRevenue": total_revenue,
        "activePurchases": active_purchases,
        "totalPurchases": total_purchases,
        "sessionsDelivered": sessions_delivered,
        "mostPopularPackage": most_popular,
    }
