from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma

from app import (
    PaginationParams,
    ServiceCreate,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdate,
    create_service,
    delete_service,
    get_admin_user,
    get_db,
    get_or_404,
    get_services,
    pagination_params,
    update_service,
)

router = APIRouter(prefix="/services", tags=["Services"])


@router.get("", response_model=ServiceListResponse)
async def list_services(
    category: str | None = None,
    pagination: PaginationParams = Depends(pagination_params),
    db: Prisma = Depends(get_db),
):
    services, total = await get_services(db, category=category, **pagination)
    return ServiceListResponse(
        services=[ServiceResponse.model_validate(s) for s in services],
        total=total,
    )


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service_by_id(
    service_id: str,
    db: Prisma = Depends(get_db),
):
    service = await get_or_404(db, "service", service_id)
    return ServiceResponse.model_validate(service)


@router.post(
    "",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_service(
    data: ServiceCreate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    service = await create_service(db, data.model_dump())
    return ServiceResponse.model_validate(service)


@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service_by_id(
    service_id: str,
    data: ServiceUpdate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "service", service_id)
    updated = await update_service(
        db, service_id, data.model_dump(exclude_none=True)
    )
    return ServiceResponse.model_validate(updated)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_by_id(
    service_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "service", service_id)
    await delete_service(db, service_id)
