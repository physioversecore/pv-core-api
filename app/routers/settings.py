import json

from fastapi import APIRouter, Depends
from prisma import Prisma

from app import get_current_user, get_db
from app.deps import get_admin_user
from app.models.settings import DesignTokensPayload
from app.services.settings import get_setting, upsert_setting

router = APIRouter(prefix="/settings", tags=["Settings"])

DESIGN_TOKENS_KEY = "design-tokens"


@router.get("/design-tokens")
async def read_design_tokens(db: Prisma = Depends(get_db)):
    row = await get_setting(db, DESIGN_TOKENS_KEY)
    if not row:
        return {"tokens": None}
    return {"tokens": json.loads(row.jsonValue)}


@router.put("/design-tokens")
async def write_design_tokens(
    body: DesignTokensPayload,
    _admin=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await upsert_setting(db, DESIGN_TOKENS_KEY, body.tokens)
    return {"ok": True}
