from pydantic import BaseModel


class GoogleAuthRequest(BaseModel):
    credential: str
    role: str = "PATIENT"
