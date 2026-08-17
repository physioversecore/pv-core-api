from fastapi import APIRouter, Depends, status
from prisma import Prisma

from app import (
    PackageCreate,
    PackageListResponse,
    PackageResponse,
    PackageUpdate,
    create_package,
    delete_package,
    get_admin_user,
    get_package,
    get_packages,
    get_db,
    get_or_404,
    pagination_params,
    update_package,
)

router = APIRouter(prefix="/packages", tags=["Packages"])


@router.get("", response_model=PackageListResponse)
async def list_packages(
    pagination: dict = Depends(pagination_params),
    db: Prisma = Depends(get_db),
):
    packages, total = await get_packages(db, **pagination)
    return PackageListResponse(
        packages=[PackageResponse.model_validate(p) for p in packages],
        total=total,
    )


@router.get("/{package_id}", response_model=PackageResponse)
async def get_package_by_id(package_id: str, db: Prisma = Depends(get_db)):
    package = await get_or_404(db, "package", package_id)
    return PackageResponse.model_validate(package)


@router.post("", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
async def create_new_package(
    data: PackageCreate, _=Depends(get_admin_user), db: Prisma = Depends(get_db)
):
    package = await create_package(db, data.model_dump())
    return PackageResponse.model_validate(package)


@router.put("/{package_id}", response_model=PackageResponse)
async def update_package_by_id(
    package_id: str,
    data: PackageUpdate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "package", package_id)
    updated = await update_package(db, package_id, data.model_dump(exclude_none=True))
    return PackageResponse.model_validate(updated)


@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package_by_id(
    package_id: str, _=Depends(get_admin_user), db: Prisma = Depends(get_db)
):
    await get_or_404(db, "package", package_id)
    await delete_package(db, package_id)
