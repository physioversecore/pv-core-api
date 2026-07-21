from pydantic import BaseModel, ConfigDict


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class AdminDashboardStats(_CamelModel):
    total_therapists: int
    total_patients: int
    sessions_this_week: int
    pending_verifications: int


class AdminEarningsResponse(_CamelModel):
    platform_earnings: float
    description: str


class AdminRecentActivity(_CamelModel):
    id: str
    patient_name: str
    therapist_name: str
    type: str
    timestamp: str
