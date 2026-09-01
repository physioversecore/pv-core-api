from fastapi import APIRouter, Depends
from prisma import Prisma

from app import (
    ClinicBrief,
    CoverageClinic,
    CoverageResponse,
    CoverageTherapist,
    ServiceAreaBrief,
    ServiceAreaBriefListResponse,
    clinics_in_area,
    get_db,
    list_service_areas,
    therapists_covering,
)

router = APIRouter(prefix="/coverage", tags=["Coverage"])


@router.get("/areas", response_model=ServiceAreaBriefListResponse)
async def areas(db: Prisma = Depends(get_db)):
    """The area chips on the map screen.

    Public: choosing where you live is how the screen is used, and requiring
    a session to see coverage would hide the product from the people
    deciding whether to sign up.
    """
    rows = await list_service_areas(db)
    return ServiceAreaBriefListResponse(
        areas=[ServiceAreaBrief.model_validate(a) for a in rows]
    )


@router.get("/therapists", response_model=CoverageResponse)
async def coverage_for_area(
    areaId: str | None = None,
    db: Prisma = Depends(get_db),
):
    rows, area = await therapists_covering(db, areaId)
    clinic_rows, _ = await clinics_in_area(db, areaId)

    therapists = [
        CoverageTherapist(
            id=t.id,
            name=t.name or "",
            specialty=t.specialty or "",
            city=t.city or "",
            price=t.price or 0.0,
            listingType=t.listingType,
            serviceRadiusKm=t.serviceRadiusKm,
            distanceKm=round(distance, 1) if distance is not None else None,
            covers=covers,
            clinic=ClinicBrief.model_validate(t.clinic) if t.clinic else None,
        )
        for t, covers, distance in rows
    ]

    clinics = [
        CoverageClinic(
            id=c.id,
            name=c.name,
            area=c.area,
            city=c.city,
            address=c.address,
            hours=c.hours,
            distanceKm=round(d, 1) if d is not None else None,
        )
        for c, d in clinic_rows
    ]

    return CoverageResponse(
        area=ServiceAreaBrief.model_validate(area) if area else None,
        therapists=therapists,
        clinics=clinics,
        coveringCount=sum(1 for t in therapists if t.covers),
    )
