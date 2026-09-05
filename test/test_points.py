"""Points ledger and referral awards.

These rules are money-adjacent, so the tests are about the ones that cost real
value if they are wrong: paying twice, paying for a booking that never
happened, and letting someone spend more than they hold.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.points import (
    DEFAULT_CONFIG,
    get_balance,
    grant,
    redeem,
)


class FakeTable:
    """Enough of a Prisma table to exercise the ledger rules."""

    def __init__(self):
        self.rows = []
        self._seq = 0

    async def find_unique(self, where):
        for row in self.rows:
            if "idempotencyKey" in where and row.idempotencyKey == where["idempotencyKey"]:
                return row
            if "id" in where and row.id == where["id"]:
                return row
        return None

    async def find_many(self, where=None, **_):
        return [r for r in self.rows if self._matches(r, where or {})]

    async def count(self, where=None):
        return len(await self.find_many(where))

    async def create(self, data):
        self._seq += 1
        row = SimpleNamespace(
            id="tx-%d" % self._seq,
            createdAt=datetime.now(timezone.utc),
            **data,
        )
        self.rows.append(row)
        return row

    async def update(self, where, data):
        row = await self.find_unique(where)
        if row:
            for k, v in data.items():
                setattr(row, k, v)
        return row

    async def update_many(self, where, data):
        hits = await self.find_many(where)
        for row in hits:
            for k, v in data.items():
                setattr(row, k, v)
        return len(hits)

    @staticmethod
    def _matches(row, where):
        for key, want in where.items():
            got = getattr(row, key, None)
            if isinstance(want, dict) and "in" in want:
                if got not in want["in"]:
                    return False
            elif isinstance(want, dict) and "lte" in want:
                if got is None or got > want["lte"]:
                    return False
            elif isinstance(want, dict) and "gte" in want:
                if got is None or got < want["gte"]:
                    return False
            elif got != want:
                return False
        return True


class FakeUsers:
    def __init__(self, count=0):
        self._count = count

    async def count(self, where=None):
        return self._count


class FakeDb:
    def __init__(self, referred=0):
        self.pointtransaction = FakeTable()
        self.user = FakeUsers(referred)
        self.setting = self

    async def find_unique(self, where):
        return None  # no stored config -> defaults


@pytest.fixture
def db():
    return FakeDb()


class TestLedger:
    @pytest.mark.asyncio
    async def test_balance_counts_only_available_points(self, db):
        await grant(db, "u1", delta=200, type="REFERRAL_EARN", status="AVAILABLE")
        await grant(db, "u1", delta=200, type="REFERRAL_EARN", status="PENDING")

        totals = await get_balance(db, "u1")

        assert totals["balance"] == 200, "held points are not spendable"
        assert totals["pending"] == 200

    @pytest.mark.asyncio
    async def test_earned_is_a_lifetime_figure(self, db):
        await grant(db, "u1", delta=640, type="REFERRAL_EARN", status="AVAILABLE")
        await grant(db, "u1", delta=-300, type="REDEMPTION", status="AVAILABLE")

        totals = await get_balance(db, "u1")

        assert totals["earned"] == 640, "spending must not reduce lifetime earned"
        assert totals["used"] == 300
        assert totals["balance"] == 340

    @pytest.mark.asyncio
    async def test_expired_points_leave_the_balance(self, db):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        await grant(
            db, "u1", delta=100, type="PROMO_GRANT", status="AVAILABLE", expires_at=past
        )

        assert (await get_balance(db, "u1"))["balance"] == 0

    @pytest.mark.asyncio
    async def test_an_idempotency_key_cannot_credit_twice(self, db):
        first = await grant(
            db, "u1", delta=200, type="REFERRAL_EARN", idempotency_key="referral:x"
        )
        second = await grant(
            db, "u1", delta=200, type="REFERRAL_EARN", idempotency_key="referral:x"
        )

        assert first is not None
        assert second is None, "a retried award must not double-credit"
        assert (await get_balance(db, "u1"))["balance"] == 200

    @pytest.mark.asyncio
    async def test_a_zero_delta_is_not_recorded(self, db):
        assert await grant(db, "u1", delta=0, type="ADJUSTMENT") is None


class TestRedemption:
    @pytest.mark.asyncio
    async def test_cannot_spend_more_than_the_balance(self, db):
        await grant(db, "u1", delta=100, type="REFERRAL_EARN", status="AVAILABLE")

        row, error = await redeem(db, "u1", 200, session_id="s1", fee=2000)

        assert row is None
        assert "do not have" in error

    @pytest.mark.asyncio
    async def test_a_discount_cannot_exceed_half_the_fee(self, db):
        await grant(db, "u1", delta=5000, type="PROMO_GRANT", status="AVAILABLE")

        # Fee 1000 at 1 pt = Rs 1, capped at 50% -> 500 points.
        row, error = await redeem(db, "u1", 900, session_id="s1", fee=1000)

        assert row is None
        assert "up to 500" in error

    @pytest.mark.asyncio
    async def test_a_valid_redemption_debits_the_ledger(self, db):
        await grant(db, "u1", delta=1000, type="PROMO_GRANT", status="AVAILABLE")

        row, error = await redeem(db, "u1", 300, session_id="s1", fee=2000)

        assert error is None
        assert row.delta == -300
        assert (await get_balance(db, "u1"))["balance"] == 700

    @pytest.mark.asyncio
    async def test_points_cannot_be_applied_twice_to_one_booking(self, db):
        await grant(db, "u1", delta=1000, type="PROMO_GRANT", status="AVAILABLE")

        await redeem(db, "u1", 100, session_id="s1", fee=2000)
        row, error = await redeem(db, "u1", 100, session_id="s1", fee=2000)

        assert row is None
        assert "already been applied" in error

    @pytest.mark.asyncio
    async def test_zero_or_negative_is_rejected(self, db):
        row, error = await redeem(db, "u1", 0, session_id="s1", fee=2000)
        assert row is None and error


class TestDefaults:
    def test_the_spec_defaults_are_what_ships(self):
        # These are the [R] recommendations; changing one is a product call.
        # The referral amounts now follow the prototype's Refer & earn screens
        # rather than the spec's original flat Rs 200 both-sides proposal.
        assert DEFAULT_CONFIG["referralAwardPatientReferrer"] == 500
        assert DEFAULT_CONFIG["referralAwardTherapistRefersTherapist"] == 1000
        assert DEFAULT_CONFIG["referralAwardTherapistRefersPatient"] == 500
        assert DEFAULT_CONFIG["referralAwardsBothSides"] is False
        assert DEFAULT_CONFIG["holdDays"] == 7
        assert DEFAULT_CONFIG["expiryDays"] is None, "expiry is off at launch"
        assert DEFAULT_CONFIG["maxRewardedReferralsPerMonth"] == 5
        assert DEFAULT_CONFIG["maxRedemptionFractionOfFee"] == 0.5
        assert DEFAULT_CONFIG["pointToNpr"] == 1.0
