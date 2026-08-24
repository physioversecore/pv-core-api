import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse
from prisma import Prisma
from prisma.enums import Role

from app import get_current_user, get_db, settings
from app.services.auth import decode_access_token
from app.database import db
from jose import JWTError, jwt

router = APIRouter(prefix="/uploads", tags=["Uploads"])

UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "Upload"
REPORTS_ROOT = UPLOAD_ROOT / "Reports"
THERAPISTS_ROOT = UPLOAD_ROOT / "Therapists"
PATIENTS_ROOT = UPLOAD_ROOT / "Patients"
APPLICATIONS_ROOT = UPLOAD_ROOT / "TherapistApplications"
EVIDENCE_ROOT = UPLOAD_ROOT / "ComplaintEvidence"

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
# Images and PDFs only — no doc/docx uploads.
ALLOWED_REPORT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
ALLOWED_THERAPIST_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _sanitize_id(value: str) -> str:
    safe = Path(value).name
    if safe != value or ".." in value or "/" in value or "\\" in value:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    return safe


def _validate_filename(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_REPORT_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not allowed")
    return ext


def _validate_photo_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only image files are allowed for profile photo")
    return ext


async def _resolve_therapist(db: Prisma, key: str):
    """Resolve a therapist by Therapist id or User id.

    If the therapist has no Therapist profile row yet (e.g. a pending
    application created via signup), one is created lazily so document/photo
    uploads work for therapists in every status."""
    therapist = await db.therapist.find_unique(where={"id": key})
    if not therapist:
        therapist = await db.therapist.find_unique(where={"userId": key})
    if not therapist:
        user = await db.user.find_unique(where={"id": key})
        if not user:
            return None
        therapist = await db.therapist.create(
            data={
                "userId": user.id,
                "name": user.name or "Therapist",
                "specialty": user.specialty or "General",
                "city": user.city or "Kathmandu",
                "gender": "Male",
                "price": 1000.0,
                "experience": 1,
                "bio": "",
            }
        )
    return therapist


def _validate_upload_size(content: bytes) -> None:
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"File exceeds maximum size of {MAX_UPLOAD_SIZE // (1024 * 1024)}MB")


def _validate_application_session(session: str) -> str:
    safe = _sanitize_id(session)
    if len(safe) < 8 or len(safe) > 128:
        raise HTTPException(status_code=400, detail="Invalid upload session")
    return safe


@router.post("/therapist-application")
async def upload_therapist_application(
    files: list[UploadFile] = File(...),
    session: str = Form(""),
):
    """Public endpoint — lets a therapist attach verification documents during signup
    (before an account/therapist record exists). Files are stored under a client-
    generated upload session and returned as URLs to embed in the signup payload."""
    session = _validate_application_session(session or "therapist-application")

    app_dir = APPLICATIONS_ROOT / session
    app_dir.mkdir(parents=True, exist_ok=True)

    uploaded: list[dict] = []
    for f in files:
        ext = _validate_filename(f.filename or "file")
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = app_dir / filename

        content = await f.read()
        _validate_upload_size(content)

        with open(dest, "wb") as out:
            out.write(content)

        uploaded.append(
            {
                "url": f"/api/v1/uploads/applications/{session}/{filename}",
                "fileName": f.filename or f"file{ext}",
                "fileSize": len(content),
            }
        )

    return {"urls": uploaded}


@router.get("/applications/{session}/{filename}")
async def serve_application_file(
    session: str,
    filename: str,
    current_user=Depends(get_current_user),
):
    session = _validate_application_session(session)
    file_path = (APPLICATIONS_ROOT / session / filename).resolve()

    if not str(file_path).startswith(str(APPLICATIONS_ROOT.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    import mimetypes
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return FileResponse(str(file_path), media_type=media_type)


@router.get("/{patient_id}/{filename}")
async def serve_file(
    patient_id: str,
    filename: str,
    token: str = Query(...),
):
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    patient_id = _sanitize_id(patient_id)
    file_path = (REPORTS_ROOT / patient_id / filename).resolve()

    if not str(file_path).startswith(str(REPORTS_ROOT.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    if user.role == Role.PATIENT and user.id != patient_id:
        raise HTTPException(status_code=403, detail="Access denied")

    import mimetypes
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return FileResponse(str(file_path), media_type=media_type)


@router.get("/therapists/{therapist_id}/{filename}")
async def serve_therapist_file(
    therapist_id: str,
    filename: str,
    current_user=Depends(get_current_user),
):
    therapist_id = _sanitize_id(therapist_id)
    file_path = (THERAPISTS_ROOT / therapist_id / filename).resolve()

    if not str(file_path).startswith(str(THERAPISTS_ROOT.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    import mimetypes
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return FileResponse(str(file_path), media_type=media_type)


@router.post("/therapists/{therapist_id}")
async def upload_therapist_file(
    therapist_id: str,
    files: list[UploadFile] = File(...),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist_id = _sanitize_id(therapist_id)

    therapist = await _resolve_therapist(db, therapist_id)
    if not therapist:
        raise HTTPException(status_code=404, detail="Therapist not found")

    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized")

    therapist_dir = THERAPISTS_ROOT / therapist.id
    therapist_dir.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    for f in files:
        ext = Path(f.filename or "file").suffix
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = therapist_dir / filename

        content = await f.read()
        _validate_upload_size(content)
        _validate_filename(f.filename or "file")

        with open(dest, "wb") as out:
            out.write(content)

        original = f.filename or f"file{ext}"
        size = len(content)
        urls.append(f"/api/v1/uploads/therapists/{therapist.id}/{filename}?name={original}&size={size}")

    existing = [u.strip() for u in (therapist.mediaUrls or "").split(",") if u.strip()]
    all_urls = existing + urls
    await db.therapist.update(
        where={"id": therapist.id},
        data={"mediaUrls": ",".join(all_urls)},
    )

    return {"urls": urls, "total": len(all_urls)}


def _document_payload(v) -> dict:
    return {
        "id": v.id,
        "documentType": v.documentType,
        "documentUrl": v.documentUrl,
        "fileName": v.fileName,
        "fileSize": v.fileSize,
        "status": v.status,
        "note": getattr(v, "note", None),
    }


@router.post("/therapists/{therapist_id}/documents")
async def upload_therapist_documents(
    therapist_id: str,
    files: list[UploadFile] = File(...),
    documentType: str = Form("Additional document"),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    """Upload verification documents for a therapist (own profile or admin).

    Files are stored in the same Therapist folder used by the application
    uploads and appended to the therapist's Verification records, so they show
    up alongside the original signup documents in admin review and on the
    therapist profile page."""
    therapist_id = _sanitize_id(therapist_id)

    therapist = await _resolve_therapist(db, therapist_id)
    if not therapist:
        raise HTTPException(status_code=404, detail="Therapist not found")

    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.role == Role.THERAPIST and therapist.userId != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    therapist_dir = THERAPISTS_ROOT / therapist.id
    therapist_dir.mkdir(parents=True, exist_ok=True)

    created: list[dict] = []
    for f in files:
        original = f.filename or "file"
        ext = _validate_filename(original)
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = therapist_dir / filename

        content = await f.read()
        _validate_upload_size(content)

        with open(dest, "wb") as out:
            out.write(content)

        url = f"/api/v1/uploads/therapists/{therapist.id}/{filename}?name={original}&size={len(content)}"

        record = await db.verification.create(
            data={
                "therapistId": therapist.id,
                "documentType": documentType[:64],
                "documentUrl": url,
                "fileName": original,
                "fileSize": len(content),
                "status": "Pending review",
                "reportedBy": "Admin" if current_user.role == Role.ADMIN else "Therapist",
                "phone": current_user.phone,
            }
        )
        created.append(_document_payload(record))

    return {"documents": created}


@router.post("/therapists/{therapist_id}/photo")
async def upload_therapist_photo(
    therapist_id: str,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    """Upload a profile photo for a therapist (own profile or admin).

    The photo becomes the first entry in the therapist's mediaUrls, so it is
    served as the avatar everywhere the profile is shown. Works for therapists
    in every status (a missing Therapist profile row is created lazily)."""
    therapist_id = _sanitize_id(therapist_id)

    therapist = await _resolve_therapist(db, therapist_id)
    if not therapist:
        raise HTTPException(status_code=404, detail="Therapist not found")

    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.role == Role.THERAPIST and therapist.userId != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    original = file.filename or "photo"
    ext = _validate_photo_extension(original)

    content = await file.read()
    _validate_upload_size(content)

    therapist_dir = THERAPISTS_ROOT / therapist.id
    therapist_dir.mkdir(parents=True, exist_ok=True)

    filename = f"photo-{uuid.uuid4().hex}{ext}"
    dest = therapist_dir / filename
    with open(dest, "wb") as out:
        out.write(content)

    url = f"/api/v1/uploads/therapists/{therapist.id}/{filename}?name={original}&size={len(content)}"

    existing = [u.strip() for u in (therapist.mediaUrls or "").split(",") if u.strip()]
    all_urls = [url] + [u for u in existing if u != url]
    await db.therapist.update(
        where={"id": therapist.id},
        data={"mediaUrls": ",".join(all_urls)},
    )

    return {"url": url}


@router.delete("/therapists/{therapist_id}/photo")
async def delete_therapist_photo(
    therapist_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    """Remove the profile photo for a therapist (own profile or admin).

    Deletes any stored ``photo-*`` file from disk and strips it from the
    therapist's mediaUrls, so the avatar disappears everywhere on the next
    refresh."""
    therapist_id = _sanitize_id(therapist_id)

    therapist = await _resolve_therapist(db, therapist_id)
    if not therapist:
        raise HTTPException(status_code=404, detail="Therapist not found")

    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.role == Role.THERAPIST and therapist.userId != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    existing = [u.strip() for u in (therapist.mediaUrls or "").split(",") if u.strip()]
    removed = [u for u in existing if u.split("/")[-1].split("?")[0].startswith("photo-")]
    kept = [u for u in existing if u not in removed]

    therapist_dir = THERAPISTS_ROOT / therapist.id
    for url in removed:
        filename = url.split("?")[0].split("/")[-1]
        file_path = (therapist_dir / filename).resolve()
        if str(file_path).startswith(str(THERAPISTS_ROOT.resolve())) and file_path.is_file():
            file_path.unlink(missing_ok=True)

    await db.therapist.update(
        where={"id": therapist.id},
        data={"mediaUrls": ",".join(kept)},
    )

    return {"success": True, "removed": len(removed)}


# ---------------------------------------------------------------------------
# Patient profile photo
# ---------------------------------------------------------------------------

@router.post("/patients/{patient_id}/photo")
async def upload_patient_photo(
    patient_id: str,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    """Upload a profile photo for a patient (own profile or admin)."""
    patient_id = _sanitize_id(patient_id)

    profile = await db.patientprofile.find_unique(where={"id": patient_id})
    if not profile:
        profile = await db.patientprofile.find_unique(where={"userId": patient_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    if current_user.role not in (Role.PATIENT, Role.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized")
    if current_user.role == Role.PATIENT and profile.userId != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    original = file.filename or "photo"
    ext = _validate_photo_extension(original)

    content = await file.read()
    _validate_upload_size(content)

    patient_dir = PATIENTS_ROOT / profile.id
    patient_dir.mkdir(parents=True, exist_ok=True)

    # Remove old photo if exists
    if profile.photo:
        old_filename = profile.photo.split("?")[0].split("/")[-1]
        old_path = (patient_dir / old_filename).resolve()
        if str(old_path).startswith(str(PATIENTS_ROOT.resolve())) and old_path.is_file():
            old_path.unlink(missing_ok=True)

    filename = f"photo-{uuid.uuid4().hex}{ext}"
    dest = patient_dir / filename
    with open(dest, "wb") as out:
        out.write(content)

    url = f"/api/v1/uploads/patients/{profile.id}/{filename}?name={original}&size={len(content)}"

    await db.patientprofile.update(
        where={"id": profile.id},
        data={"photo": url},
    )

    return {"url": url}


@router.delete("/patients/{patient_id}/photo")
async def delete_patient_photo(
    patient_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    """Remove the profile photo for a patient (own profile or admin)."""
    patient_id = _sanitize_id(patient_id)

    profile = await db.patientprofile.find_unique(where={"id": patient_id})
    if not profile:
        profile = await db.patientprofile.find_unique(where={"userId": patient_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    if current_user.role not in (Role.PATIENT, Role.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized")
    if current_user.role == Role.PATIENT and profile.userId != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if profile.photo:
        filename = profile.photo.split("?")[0].split("/")[-1]
        file_path = (PATIENTS_ROOT / profile.id / filename).resolve()
        if str(file_path).startswith(str(PATIENTS_ROOT.resolve())) and file_path.is_file():
            file_path.unlink(missing_ok=True)

    await db.patientprofile.update(
        where={"id": profile.id},
        data={"photo": None},
    )

    return {"success": True}


@router.get("/patients/{patient_id}/{filename}")
async def serve_patient_file(
    patient_id: str,
    filename: str,
    current_user=Depends(get_current_user),
):
    """Serve patient profile files (authenticated)."""
    patient_id = _sanitize_id(patient_id)
    file_path = (PATIENTS_ROOT / patient_id / filename).resolve()

    if not str(file_path).startswith(str(PATIENTS_ROOT.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    import mimetypes
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return FileResponse(str(file_path), media_type=media_type)


# ---------------------------------------------------------------------------
# Complaint evidence uploads — session-based, same pattern as therapist-application
# ---------------------------------------------------------------------------

@router.post("/complaint-evidence")
async def upload_complaint_evidence(
    files: list[UploadFile] = File(...),
    session: str = Form(""),
):
    """Public endpoint — upload evidence files before complaint creation.
    Files are stored under a client-generated session key and returned as
    real URLs to embed in the complaint payload."""
    session = _validate_application_session(session or "complaint-evidence")

    evidence_dir = EVIDENCE_ROOT / session
    evidence_dir.mkdir(parents=True, exist_ok=True)

    uploaded: list[dict] = []
    for f in files:
        ext = _validate_filename(f.filename or "file")
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = evidence_dir / filename

        content = await f.read()
        _validate_upload_size(content)

        with open(dest, "wb") as out:
            out.write(content)

        uploaded.append(
            {
                "url": f"/api/v1/uploads/evidence/{session}/{filename}",
                "fileName": f.filename or f"file{ext}",
                "fileSize": len(content),
            }
        )

    return {"urls": uploaded}


@router.get("/evidence/{session}/{filename}")
async def serve_evidence_file(
    session: str,
    filename: str,
    current_user=Depends(get_current_user),
):
    """Serve complaint evidence files (authenticated)."""
    session = _validate_application_session(session)
    file_path = (EVIDENCE_ROOT / session / filename).resolve()

    if not str(file_path).startswith(str(EVIDENCE_ROOT.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    import mimetypes
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return FileResponse(str(file_path), media_type=media_type)
