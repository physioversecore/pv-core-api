import json

from fastapi import APIRouter, Depends
from prisma import Prisma

from app import get_current_user, get_db
from app.deps import get_admin_user
from app.models.settings import (
    CurrenciesPayload,
    DesignTokensPayload,
    PaymentMethodsPayload,
)
from app.services.settings import get_setting, upsert_setting

router = APIRouter(prefix="/settings", tags=["Settings"])

DESIGN_TOKENS_KEY = "design-tokens"
CURRENCIES_KEY = "currencies"
PAYMENT_METHODS_KEY = "payment-methods"


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


@router.get("/currencies")
async def read_currencies(db: Prisma = Depends(get_db)):
    row = await get_setting(db, CURRENCIES_KEY)
    if not row:
        return {"currencies": []}
    return {"currencies": json.loads(row.jsonValue)}


@router.put("/currencies")
async def write_currencies(
    body: CurrenciesPayload,
    _admin=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    data = [c.model_dump() for c in body.currencies]
    await upsert_setting(db, CURRENCIES_KEY, data)
    return {"ok": True}


@router.get("/payment-methods")
async def read_payment_methods(db: Prisma = Depends(get_db)):
    row = await get_setting(db, PAYMENT_METHODS_KEY)
    if not row:
        return {"methods": []}
    return {"methods": json.loads(row.jsonValue)}


@router.put("/payment-methods")
async def write_payment_methods(
    body: PaymentMethodsPayload,
    _admin=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    data = [m.model_dump() for m in body.methods]
    await upsert_setting(db, PAYMENT_METHODS_KEY, data)
    return {"ok": True}
