from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from prisma import Prisma

from app import get_admin_user, get_current_user, get_db
from app.models.package_purchase import (
    AdminPackagePurchaseResponse,
    AdminPackageStatsResponse,
    PackagePurchaseDetailResponse,
    PackagePurchaseListAdminResponse,
    PackagePurchaseListResponse,
    PackagePurchaseRequest,
    PackagePurchaseResponse,
)
from app.services.package_purchase import (
    get_active_purchase,
    get_admin_package_purchases,
    get_admin_package_stats,
    get_user_purchases,
    purchase_package,
)
from app.services.notification import log_admin_notification

router = APIRouter(prefix="/packages", tags=["Packages"])
admin_router = APIRouter(prefix="/admin/packages", tags=["Admin Packages"])


@router.post(
    "/{package_id}/purchase",
    response_model=PackagePurchaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def buy_package(
    package_id: str,
    data: PackagePurchaseRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role != "PATIENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can purchase packages",
        )

    try:
        result = await purchase_package(
            db, current_user.id, package_id, data.paymentMethod
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    await log_admin_notification(
        db,
        category="payment",
        message=f"Package purchased: {result['packageName']} by {current_user.name}",
        action_type="package",
        action_id=result["id"],
    )

    from app.services.email.notifications import send_package_purchased_email

    background_tasks.add_task(
        send_package_purchased_email,
        email=current_user.email,
        name=current_user.name,
        package_name=result["packageName"],
        session_count=result["sessionsTotal"],
        validity_days=result["validityDays"],
        amount=f"Rs {result['amount']:,.0f}" if result.get("amount") else "Rs 0",
    )

    return PackagePurchaseResponse(**result)


@router.get("/my-purchases", response_model=PackagePurchaseListResponse)
async def list_my_purchases(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    purchases = await get_user_purchases(db, current_user.id)
    return PackagePurchaseListResponse(
        purchases=[PackagePurchaseResponse(**p) for p in purchases],
        total=len(purchases),
    )


@router.get("/my-purchases/active", response_model=PackagePurchaseDetailResponse)
async def get_my_active_purchase(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    purchase = await get_active_purchase(db, current_user.id)
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active package found",
        )
    return PackagePurchaseDetailResponse(**purchase)


@admin_router.get("/purchases", response_model=PackagePurchaseListAdminResponse)
async def admin_list_purchases(
    skip: int = 0,
    limit: int = 10,
    status: str | None = None,
    packageId: str | None = None,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    items, total = await get_admin_package_purchases(
        db,
        skip=skip,
        limit=limit,
        status=status,
        package_id=packageId,
    )
    return PackagePurchaseListAdminResponse(
        purchases=[AdminPackagePurchaseResponse(**i) for i in items],
        total=total,
    )


@admin_router.get("/stats", response_model=AdminPackageStatsResponse)
async def admin_package_stats(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    stats = await get_admin_package_stats(db)
    return AdminPackageStatsResponse(**stats)