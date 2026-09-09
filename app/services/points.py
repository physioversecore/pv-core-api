"""Referral and loyalty points.

The ledger is append-only: every earn, spend, reversal and expiry is a row, and
the balance is a sum over them. A mutable counter would give no audit trail, no
way to answer "why is my balance this", and would race on concurrent redemption.

Money-adjacent rules that live here rather than in the router:

* Points are awarded on a *completed* session, not a booked one -- book-then-
  cancel is otherwise free money.
* Awards land PENDING and mature after a hold, so a refund can void them before
  they were ever spendable.
* Every award carries an idempotency key, so a retried request cannot credit
  twice.
"""
import json
from datetime import datetime, timedelta, timezone

from prisma import Prisma

CONFIG_KEY = "points_config"

DEFAULT_CONFIG = {
    # Rs per point. Stored rather than hardcoded so it can change without a
    # deploy; never re-rate points already earned.
    "pointToNpr": 1.0,
    # Tiered by who refers whom, per the prototype's Refer & earn screens: a
    # patient earns Rs 500 a friend, while a therapist earns Rs 1,000 for
    # bringing another therapist and Rs 500 for bringing a patient. Kept as
    # separate keys rather than one number so the therapist tier can move
    # without touching the patient one.
    "referralAwardPatientReferrer": 500,
    "referralAwardTherapistRefersTherapist": 1000,
    "referralAwardTherapistRefersPatient": 500,
    # The prototype shows one figure, the referrer's -- the referee is not
    # paid for being invited.
    "referralAwardsBothSides": False,
    # Retained so an existing stored config still resolves, and as the value
    # used when a role pairing is not one of the three above.
    "referralAwardPoints": 500,
    # Days an award stays PENDING before it can be spent.
    "holdDays": 7,
    # None disables expiry. Off at launch: easy to switch on for newly earned
    # points later, ugly to explain if applied retroactively.
    "expiryDays": None,
    "maxRewardedReferralsPerMonth": 5,
    "maxRewardedReferralsLifetime": 50,
    # A discount may never zero a session, which would create refund and payout
    # edges.
    "maxRedemptionFractionOfFee": 0.5,
}


async def get_config(db: Prisma) -> dict:
    row = await db.setting.find_unique(where={"key": CONFIG_KEY})
    if not row:
        return DEFAULT_CONFIG.copy()
    return {**DEFAULT_CONFIG, **json.loads(row.jsonValue)}


async def save_config(db: Prisma, data: dict) -> dict:
    current = await get_config(db)
    merged = {**current, **{k: v for k, v in data.items() if v is not None}}
    await db.setting.upsert(
        where={"key": CONFIG_KEY},
        data={
            "create": {"key": CONFIG_KEY, "jsonValue": json.dumps(merged)},
            "update": {"jsonValue": json.dumps(merged)},
        },
    )
    return merged


# -- Balance ----------------------------------------------------------------


async def get_balance(db: Prisma, user_id: str) -> dict:
    """Balance plus the three totals the rewards screen shows."""
    now = datetime.now(timezone.utc)
    rows = await db.pointtransaction.find_many(where={"userId": user_id})

    available = earned = used = pending = 0
    for row in rows:
        unexpired = row.expiresAt is None or row.expiresAt > now
        if row.status == "AVAILABLE" and unexpired:
            available += row.delta
        if row.status == "PENDING":
            pending += row.delta
        # Earned and used are lifetime figures and deliberately ignore expiry:
        # "you have earned 640" should not shrink because some lapsed.
        if row.delta > 0 and row.status in ("AVAILABLE", "PENDING"):
            earned += row.delta
        if row.delta < 0 and row.status == "AVAILABLE":
            used += -row.delta

    referred = await db.user.count(where={"referredById": user_id})

    return {
        "balance": available,
        "pending": pending,
        "earned": earned,
        "used": used,
        "referred": referred,
    }


async def list_transactions(db: Prisma, user_id: str, skip=0, limit=50):
    where = {"userId": user_id}
    items = await db.pointtransaction.find_many(
        where=where, skip=skip, take=limit, order={"createdAt": "desc"}
    )
    total = await db.pointtransaction.count(where=where)
    return items, total


# -- Writing to the ledger --------------------------------------------------


async def _exists(db: Prisma, idempotency_key: str) -> bool:
    if not idempotency_key:
        return False
    found = await db.pointtransaction.find_unique(
        where={"idempotencyKey": idempotency_key}
    )
    return found is not None


async def grant(
    db: Prisma,
    user_id: str,
    *,
    delta: int,
    type: str,
    status: str = "AVAILABLE",
    reason: str | None = None,
    ref_type: str | None = None,
    ref_id: str | None = None,
    idempotency_key: str | None = None,
    expires_at: datetime | None = None,
):
    if delta == 0:
        return None
    if idempotency_key and await _exists(db, idempotency_key):
        return None  # already credited; a retry must not double up
    return await db.pointtransaction.create(
        data={
            "userId": user_id,
            "delta": delta,
            "type": type,
            "status": status,
            "reason": reason,
            "refType": ref_type,
            "refId": ref_id,
            "idempotencyKey": idempotency_key,
            "expiresAt": expires_at,
        }
    )


async def _rewarded_referral_count(db: Prisma, user_id: str, since):
    where = {
        "userId": user_id,
        "type": "REFERRAL_EARN",
        "status": {"in": ["PENDING", "AVAILABLE"]},
    }
    if since:
        where["createdAt"] = {"gte": since}
    return await db.pointtransaction.count(where=where)


async def _within_caps(db: Prisma, referrer_id: str, config: dict) -> bool:
    month_cap = int(config["maxRewardedReferralsPerMonth"])
    life_cap = int(config["maxRewardedReferralsLifetime"])

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if month_cap:
        used = await _rewarded_referral_count(db, referrer_id, month_start)
        if used >= month_cap:
            return False
    if life_cap:
        used = await _rewarded_referral_count(db, referrer_id, None)
        if used >= life_cap:
            return False
    return True



def _referral_amount(config: dict, referrer, referee) -> int:
    """What the referrer earns, by the roles of both parties.

    A missing referrer or an unrecognised pairing falls back to the flat
    `referralAwardPoints` rather than paying nothing, so a role added later
    still rewards the person who brought someone in.
    """
    referrer_role = getattr(referrer, "role", None)
    referee_role = getattr(referee, "role", None)

    if referrer_role == "THERAPIST":
        if referee_role == "THERAPIST":
            return int(config["referralAwardTherapistRefersTherapist"])
        return int(config["referralAwardTherapistRefersPatient"])
    if referrer_role == "PATIENT":
        return int(config["referralAwardPatientReferrer"])
    return int(config["referralAwardPoints"])

async def award_referral_for_session(db: Prisma, session) -> list:
    """Award both sides when a referred patient completes their first session.

    Returns the rows created so the caller can raise notifications for them.
    Safe to call repeatedly: the idempotency key is the referred user's id, so
    only the first completed session ever pays out.
    """
    config = await get_config(db)

    patient = await db.user.find_unique(where={"id": session.patientId})
    if not patient or not patient.referredById:
        return []

    referrer = await db.user.find_unique(where={"id": patient.referredById})
    amount = _referral_amount(config, referrer, patient)
    if amount <= 0:
        return []

    # One payout per referred user, ever -- not per completed session.
    key_referrer = "referral:{}:referrer".format(patient.id)
    key_referee = "referral:{}:referee".format(patient.id)
    if await _exists(db, key_referrer):
        return []

    if not await _within_caps(db, patient.referredById, config):
        return []

    hold_days = int(config["holdDays"])
    expiry_days = config.get("expiryDays")
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=int(expiry_days)) if expiry_days else None
    # PENDING when a hold is configured, so a refund can void the award before
    # it was ever spendable.
    landing_status = "PENDING" if hold_days > 0 else "AVAILABLE"

    created = []
    row = await grant(
        db,
        patient.referredById,
        delta=amount,
        type="REFERRAL_EARN",
        status=landing_status,
        reason="Referral: {} completed their first session".format(patient.name),
        ref_type="SESSION",
        ref_id=session.id,
        idempotency_key=key_referrer,
        expires_at=expires_at,
    )
    if row:
        created.append((patient.referredById, row))

    if config.get("referralAwardsBothSides"):
        row = await grant(
            db,
            patient.id,
            delta=amount,
            type="REFERRAL_EARN",
            status=landing_status,
            reason="Welcome bonus: your first completed session",
            ref_type="SESSION",
            ref_id=session.id,
            idempotency_key=key_referee,
            expires_at=expires_at,
        )
        if row:
            created.append((patient.id, row))

    return created


async def mature_pending(db: Prisma, user_id: str) -> int:
    """Move held awards to AVAILABLE once the hold has elapsed.

    Done on read rather than by a scheduler: a balance is only observed when
    someone looks at it, so a cron job would buy nothing and add a moving part
    to operate.
    """
    config = await get_config(db)
    hold_days = int(config["holdDays"])
    cutoff = datetime.now(timezone.utc) - timedelta(days=hold_days)
    return await db.pointtransaction.update_many(
        where={"userId": user_id, "status": "PENDING", "createdAt": {"lte": cutoff}},
        data={"status": "AVAILABLE"},
    )


async def reverse_for_session(db: Prisma, session_id: str, reason: str) -> int:
    """Void awards tied to a session that was cancelled or refunded.

    A negative adjustment rather than a delete, so the original stays legible
    in the ledger.
    """
    rows = await db.pointtransaction.find_many(
        where={
            "refType": "SESSION",
            "refId": session_id,
            "type": "REFERRAL_EARN",
            "status": {"in": ["PENDING", "AVAILABLE"]},
        }
    )
    for row in rows:
        await db.pointtransaction.update(
            where={"id": row.id}, data={"status": "REVERSED"}
        )
        await grant(
            db,
            row.userId,
            delta=-row.delta,
            type="ADJUSTMENT",
            status="AVAILABLE",
            reason=reason,
            ref_type="SESSION",
            ref_id=session_id,
            idempotency_key="reverse:{}".format(row.id),
        )
    return len(rows)


async def redeem(db: Prisma, user_id: str, points: int, *, session_id: str, fee: float):
    """Spend points against a booking. Returns (transaction, error)."""
    if points <= 0:
        return None, "Enter how many points to use"

    config = await get_config(db)
    await mature_pending(db, user_id)

    balance = (await get_balance(db, user_id))["balance"]
    if points > balance:
        return None, "You do not have that many points"

    rate = float(config["pointToNpr"])
    cap_fraction = float(config["maxRedemptionFractionOfFee"])
    max_points = int((fee * cap_fraction) / rate) if rate > 0 else 0
    if max_points <= 0:
        return None, "Points cannot be used on this booking"
    if points > max_points:
        return None, "You can use up to {} points on this booking".format(max_points)

    row = await grant(
        db,
        user_id,
        delta=-points,
        type="REDEMPTION",
        status="AVAILABLE",
        reason="Applied to a session booking",
        ref_type="SESSION",
        ref_id=session_id,
        idempotency_key="redeem:{}".format(session_id),
    )
    if row is None:
        return None, "Points have already been applied to this booking"
    return row, None
