from pydantic import BaseModel


class NextSessionInfo(BaseModel):
    id: str
    therapistName: str
    therapistId: str
    date: str
    time: str
    type: str
    status: str


class PatientDashboardResponse(BaseModel):
    name: str
    totalSessions: int
    completedSessions: int
    upcomingSessions: int
    nextSession: NextSessionInfo | None = None
    referralCode: str
    referralLink: str

    class Config:
        from_attributes = True


class ReferralResponse(BaseModel):
    code: str
    link: str
