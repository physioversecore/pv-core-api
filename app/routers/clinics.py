from fastapi import APIRouter, Depends, status
from prisma import Prisma

from app import (
    ClinicCreate,
    ClinicListResponse,
    ClinicResponse,
    ClinicUpdate,
    create_clinic,
    delete_clinic,
    get_admin_user,
    get_clinic,
    get_clinics,
    get_db,
    get_or_404,
    pagination_params,
    update_clinic,
)

router = APIRouter(prefix="/clinics", tags=["Clinics"])


@router.get("", response_model=ClinicListResponse)
async def list_clinics(
    search: str | None = None,
    city: str | None = None,
    pagination: dict = Depends(pagination_params),
    db: Prisma = Depends(get_db),
):
    clinics, total = await get_clinics(db, search=search, city=city, **pagination)
    return ClinicListResponse(
        clinics=[ClinicResponse.model_validate(c) for c in clinics],
        total=total,
    )


@router.get("/{clinic_id}", response_model=ClinicResponse)
async def get_clinic_by_id(clinic_id: str, db: Prisma = Depends(get_db)):
    clinic = await get_or_404(db, "clinic", clinic_id)
    return ClinicResponse.model_validate(clinic)


@router.post("", response_model=ClinicResponse, status_code=status.HTTP_201_CREATED)
async def create_new_clinic(data: ClinicCreate, _=Depends(get_admin_user), db: Prisma = Depends(get_db)):
    clinic = await create_clinic(db, data.model_dump())
    return ClinicResponse.model_validate(clinic)


@router.put("/{clinic_id}", response_model=ClinicResponse)
async def update_clinic_by_id(
    clinic_id: str,
    data: ClinicUpdate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "clinic", clinic_id)
    updated = await update_clinic(db, clinic_id, data.model_dump(exclude_none=True))
    return ClinicResponse.model_validate(updated)


@router.delete("/{clinic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clinic_by_id(clinic_id: str, _=Depends(get_admin_user), db: Prisma = Depends(get_db)):
    await get_or_404(db, "clinic", clinic_id)
    await delete_clinic(db, clinic_id)
