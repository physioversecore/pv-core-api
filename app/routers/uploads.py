from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/uploads", tags=["Uploads"])

UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "Upload"
REPORTS_ROOT = UPLOAD_ROOT / "Reports"


@router.get("/{patient_id}/{filename}")
async def serve_file(patient_id: str, filename: str):
    file_path = REPORTS_ROOT / patient_id / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    import mimetypes
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

    return FileResponse(str(file_path), media_type=media_type)
