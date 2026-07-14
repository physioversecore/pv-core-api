from pydantic import BaseModel


class DesignTokensPayload(BaseModel):
    tokens: dict


class SettingResponse(BaseModel):
    key: str
    jsonValue: str
