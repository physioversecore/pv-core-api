from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PointBalanceResponse(BaseModel):
    """What the rewards screen shows above the fold."""

    balance: int
    pending: int
    earned: int
    used: int
    referred: int

    # Rs equivalent, so the client does not hardcode the rate.
    pointToNpr: float


class PointTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    delta: int
    type: str
    status: str
    reason: str | None = None
    refType: str | None = None
    refId: str | None = None
    expiresAt: datetime | None = None
    createdAt: datetime


class PointTransactionListResponse(BaseModel):
    transactions: list[PointTransactionResponse]
    total: int


class ReferralEntry(BaseModel):
    """One row of the referral history list."""

    id: str
    name: str

    # INVITED -> JOINED -> PENDING -> REWARDED (or REVERSED)
    state: str
    points: int | None = None
    joinedAt: datetime | None = None


class ReferralSummaryResponse(BaseModel):
    code: str
    link: str

    # The headline rate for *this* viewer's role -- a therapist earns more for
    # bringing another therapist than a patient earns for bringing a friend.
    awardPoints: int

    # "TOTAL EARNED" on the design: everything this user has been granted for
    # referrals, held and available alike.
    totalEarned: int = 0

    referrals: list[ReferralEntry]


class PointGrantRequest(BaseModel):
    """Admin grant. Bulk by design -- festival bonuses go to many at once."""

    userIds: list[str] = Field(min_length=1, max_length=1000)
    amount: int = Field(ge=-100000, le=100000)
    reason: str = Field(min_length=1, max_length=200)
    expiresAt: datetime | None = None


class PointGrantResponse(BaseModel):
    granted: int
    skipped: int


class PointsConfig(BaseModel):
    pointToNpr: float | None = Field(default=None, gt=0, le=1000)
    referralAwardPoints: int | None = Field(default=None, ge=0, le=100000)
    referralAwardsBothSides: bool | None = None
    holdDays: int | None = Field(default=None, ge=0, le=365)
    expiryDays: int | None = Field(default=None, ge=0, le=3650)
    maxRewardedReferralsPerMonth: int | None = Field(default=None, ge=0, le=10000)
    maxRewardedReferralsLifetime: int | None = Field(default=None, ge=0, le=100000)
    maxRedemptionFractionOfFee: float | None = Field(default=None, gt=0, le=1)


class ApplyPointsRequest(BaseModel):
    points: int = Field(ge=1, le=1000000)


class ApplyPointsResponse(BaseModel):
    pointsApplied: int
    discountAmount: float

    # The therapist is still paid the full fee -- the platform funds the
    # discount. Returned so the client can show both figures honestly.
    sessionFee: float
    payable: float
