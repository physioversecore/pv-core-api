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
    get_reports_for_therapist,
    pagination_params,
    update_report,
)

router = APIRouter(prefix="/reports", tags=["Reports"])

REPORTS_ROOT = Path(__file__).resolve().parent.parent.parent / "Upload" / "Reports"

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx"}


def _sanitize_id(value: str) -> str:
    safe = Path(value).name
    if safe != value or ".." in value or "/" in value or "\\" in value:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    return safe


async def _save_files(patient_id: str, files: list[UploadFile]) -> list[str]:
    patient_id = _sanitize_id(patient_id)
    patient_dir = REPORTS_ROOT / patient_id
    patient_dir.mkdir(parents=False, exist_ok=True)

    urls: list[str] = []
    for f in files:
        ext = Path(f.filename or "file").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"File type '{ext}' not allowed")

        content = await f.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="File exceeds 10MB limit")

        filename = f"{uuid.uuid4().hex}{ext}"
        dest = patient_dir / filename

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

        # resolve therapistId from the current user
        therapist = await db.therapist.find_unique(where={"userId": current_user.id})

        report = await create_report(db, {
            "patientId": patientId,
            **({"therapistId": therapist.id} if therapist else {}),
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


# ── list reports for therapist (all their patients) ──


@router.get("/therapist")
async def list_therapist_reports(
    pagination: PaginationParams = Depends(pagination_params),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    reports, total = await get_reports_for_therapist(
        db, current_user.id, **pagination
    )

    def _report_to_dict(r):
        return {
            "id": r.id,
            "patientId": r.patientId,
            "sessionId": r.sessionId,
            "title": r.title,
            "content": r.content or "",
            "fileUrl": r.fileUrl,
            "patient": r.patient.name if r.patient else "Unknown",
            "files": [u.strip() for u in r.fileUrl.split(",") if u.strip()] if r.fileUrl else [],
            "date": r.createdAt.strftime("%-d %b"),
            "createdAt": r.createdAt.isoformat(),
            "updatedAt": r.updatedAt.isoformat(),
        }

    return {
        "reports": [_report_to_dict(r) for r in reports],
        "total": total,
    }


# ── single report ──


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_by_id(
    report_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    report = await get_or_404(db, "report", report_id)
    if current_user.role == Role.PATIENT and report.patientId != current_user.id:
        raise HTTPException(status_code=404, detail="Report not found")
    if current_user.role == Role.THERAPIST:
        therapist = await db.therapist.find_unique(where={"userId": current_user.id})
        if not therapist or report.therapistId != therapist.id:
            raise HTTPException(status_code=404, detail="Report not found")
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
    report = await get_or_404(db, "report", report_id)
    if current_user.role == Role.THERAPIST:
        therapist = await db.therapist.find_unique(where={"userId": current_user.id})
        if not therapist or report.therapistId != therapist.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
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
    report = await get_or_404(db, "report", report_id)
    if current_user.role == Role.THERAPIST:
        therapist = await db.therapist.find_unique(where={"userId": current_user.id})
        if not therapist or report.therapistId != therapist.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await delete_report(db, report_id)
