from pydantic import BaseModel


class DesignTokensPayload(BaseModel):
    tokens: dict


class SettingResponse(BaseModel):
    key: str
    jsonValue: str


class Currency(BaseModel):
    code: str
    name: str
    flag: str
    symbol: str
    rate: float


class CurrenciesPayload(BaseModel):
    currencies: list[Currency]


class PaymentMethod(BaseModel):
    id: str
    label: str
    icon: str
    type: str
    subtype: str | None = None


class PaymentMethodsPayload(BaseModel):
    methods: list[PaymentMethod]
