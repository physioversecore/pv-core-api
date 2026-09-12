from pydantic import BaseModel


class SlotUpdate(BaseModel):
    date: str
    time: str
    status: str


class BulkSlotUpdate(BaseModel):
    slots: list[SlotUpdate]


class RecurringPatternCreate(BaseModel):
    days: list[int]
    sessions: list[str]


class OpenFullMonthRequest(BaseModel):
    days: list[int]
    sessions: list[str]
    month: int
    year: int


class BlockDateRequest(BaseModel):
    date: str
    sessions: list[str] | None = None


class WorkingHoursUpdate(BaseModel):
    start: str
    end: str
    slotInterval: int = 120
    sessionDuration: int = 60
    breakDuration: int = 0
    daysOfWeek: list[str] = []


class SlotInfo(BaseModel):
    date: str
    time: str
    status: str
    patientName: str | None = None
    patientPhone: str | None = None
    sessionType: str = ""
    fee: float | None = None
    sessionId: str | None = None


class MonthlyGridResponse(BaseModel):
    month: str
    year: int
    slots: list[SlotInfo]


class WorkingHoursResponse(BaseModel):
    start: str
    end: str
    slotInterval: int = 120
    sessionDuration: int = 60
    breakDuration: int = 0
    daysOfWeek: list[str] = []


class SlotUpdateResponse(BaseModel):
    updated: int


class RecurringPatternResponse(BaseModel):
    id: str
    therapistId: str
    days: list[int]
    sessions: list[str]
    isActive: bool
    createdAt: str

    class Config:
        from_attributes = True


class RecurringPatternListResponse(BaseModel):
    patterns: list[RecurringPatternResponse]


class RecurringApplyResponse(BaseModel):
    affected: int
    skippedPast: int
    patternId: str


class OpenMonthResponse(BaseModel):
    opened: int
    skippedBooked: int
    skippedPast: int


class BlockDateResponse(BaseModel):
    blocked: int


class ApplyScheduleRequest(BaseModel):
    recurrence: str = "weekly"
    dateFrom: str | None = None
    dateTo: str | None = None


class GenerateAvailabilityRequest(BaseModel):
    dateFrom: str
    dateTo: str | None = None
    daysOfWeek: list[str]
    startTime: str
    endTime: str
    sessionDuration: int
    breakDuration: int


class BlockRangeRequest(BaseModel):
    dateFrom: str
    dateTo: str | None = None
    daysOfWeek: list[str]
    partsOfDay: list[str]
    reason: str = "Time off"
    notify: bool = True
    blockType: str = "range"


class UnblockRequest(BaseModel):
    date: str
    time: str | None = None


class BlockInfoResponse(BaseModel):
    id: str
    dateFrom: str
    dateTo: str
    daysOfWeek: list[str]
    partsOfDay: list[str]
    reason: str
    notify: bool
    createdAt: str


class SlotRangeResponse(BaseModel):
    slots: list[SlotInfo]
    blocks: list[BlockInfoResponse]


class BulkSlotInfo(BaseModel):
    """One slot in a bulk answer.

    Deliberately narrower than `SlotInfo`: no patient name, phone, fee or
    session id. A bulk read is discovery's, and it must not become a way to
    read other patients' booking details out of a therapist's calendar.
    """

    date: str
    time: str
    status: str


class NextFreeSlot(BaseModel):
    date: str
    time: str


class TherapistSlotsEntry(BaseModel):
    therapistId: str
    slots: list[BulkSlotInfo]
    nextFree: NextFreeSlot | None = None
    openCount: int


class UnansweredTherapist(BaseModel):
    therapistId: str
    reason: str


class BulkSlotRangeResponse(BaseModel):
    fromDate: str
    toDate: str
    therapists: list[TherapistSlotsEntry]
    unavailable: list[UnansweredTherapist]


class BlockRangeResponse(BaseModel):
    blocked: int
    cancelledCount: int
    affectedPatients: list[str]


class AuditLogEntryResponse(BaseModel):
    id: str
    date: str
    time: str | None
    reason: str
    scope: str
    source: str
    createdAt: str
    dateTo: str | None = None
    daysOfWeek: list[str] = []
    partsOfDay: list[str] = []


class PaginatedAuditLogResponse(BaseModel):
    entries: list[AuditLogEntryResponse]
    total: int


class AuditLogCreateRequest(BaseModel):
    date: str
    time: str | None = None
    reason: str
    scope: str
    source: str
    blockId: str | None = None
