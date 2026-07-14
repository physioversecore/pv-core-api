import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from prisma.enums import Role

from app import get_current_user

router = APIRouter(prefix="/uploads", tags=["Uploads"])

UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "Upload"
REPORTS_ROOT = UPLOAD_ROOT / "Reports"
PATIENT_PROFILE_ROOT = UPLOAD_ROOT / "Patient"
THERAPIST_PROFILE_ROOT = UPLOAD_ROOT / "Therapist"
ADMIN_PROFILE_ROOT = UPLOAD_ROOT / "Admin"


@router.post("/{patient_id}", status_code=status.HTTP_201_CREATED)
async def upload_file(
    patient_id: str,
    file: UploadFile,
    current_user=Depends(get_current_user),
):
    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    patient_dir = REPORTS_ROOT / patient_id
    patient_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "file").suffix
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = patient_dir / filename

    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    url = f"/api/v1/uploads/{patient_id}/{filename}"
    return {
        "url": url,
        "filename": filename,
        "size": len(content),
    }


@router.get("/{patient_id}/{filename}")
async def serve_file(
    patient_id: str,
    filename: str,
):
    file_path = REPORTS_ROOT / patient_id / filename
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    import mimetypes
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

    from fastapi.responses import FileResponse
    return FileResponse(str(file_path), media_type=media_type)
