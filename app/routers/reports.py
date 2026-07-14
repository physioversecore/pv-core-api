import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    PaginationParams,
    ReportResponse,
    ReportUpdate,
    create_report,
    delete_report,
    get_current_user,
    get_db,
    get_or_404,
    get_reports_for_patient,
    pagination_params,
    update_report,
)

router = APIRouter(prefix="/reports", tags=["Reports"])

REPORTS_ROOT = Path(__file__).resolve().parent.parent.parent / "Upload" / "Reports"


# ── helpers ──


async def _save_files(patient_id: str, files: list[UploadFile]) -> list[str]:
    """Save uploaded files and return their URL paths with original names."""
    patient_dir = REPORTS_ROOT / patient_id
    patient_dir.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    for f in files:
        ext = Path(f.filename or "file").suffix
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = patient_dir / filename

        content = await f.read()
        with open(dest, "wb") as out:
            out.write(content)

        original = f.filename or f"file{ext}"
        size = len(content)
        urls.append(f"/api/v1/uploads/{patient_id}/{filename}?name={original}&size={size}")

    return urls


# ── create report (JSON or multipart) ──


@router.post(
    "", response_model=ReportResponse, status_code=status.HTTP_201_CREATED
)
async def create_new_report(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
    # ── form fields (ignored when JSON body is sent) ──
    patientId: str = Form(default=""),
    title: str = Form(default=""),
    content: str = Form(default=""),
    sessionId: str | None = Form(default=None),
    # ── files (optional, only in multipart) ──
    files: list[UploadFile] = File(default=[]),
):
    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    # Determine if this is a multipart upload or a JSON body.
    # FastAPI sets Form(...) defaults to "" when no form data is sent,
    # so if patientId is empty we know the client sent JSON.
    if patientId:
        # ── multipart flow: save files, build fileUrl ──
        urls = await _save_files(patientId, files)
        fileUrl = urls[0] if len(urls) == 1 else ",".join(urls) if urls else None

        report = await create_report(db, {
            "patientId": patientId,
            "title": title,
            "content": content,
            **({"sessionId": sessionId} if sessionId else {}),
            **({"fileUrl": fileUrl} if fileUrl else {}),
        })
    else:
        # ── fallback: should not happen from the new frontend,
        #    but kept for backward compat with raw JSON calls ──
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use multipart/form-data with patientId, title, content, and files",
        )

    return ReportResponse.model_validate(report)


# ── list reports ──


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    patient_id: str | None = None,
    pagination: PaginationParams = Depends(pagination_params),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role == Role.PATIENT:
        pid = current_user.id
    else:
        pid = patient_id
        if not pid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id is required for therapists and admins",
            )
    reports, _ = await get_reports_for_patient(db, pid, **pagination)
    return [ReportResponse.model_validate(r) for r in reports]


# ── single report ──


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_by_id(
    report_id: str,
    db: Prisma = Depends(get_db),
):
    report = await get_or_404(db, "report", report_id)
    return ReportResponse.model_validate(report)


# ── update / delete ──


@router.put("/{report_id}", response_model=ReportResponse)
async def update_report_by_id(
    report_id: str,
    data: ReportUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await get_or_404(db, "report", report_id)
    updated = await update_report(
        db, report_id, data.model_dump(exclude_none=True)
    )
    return ReportResponse.model_validate(updated)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report_by_id(
    report_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await get_or_404(db, "report", report_id)
    await delete_report(db, report_id)
