from .gateway import (
    COMPLETED,
    GatewayInitiation,
    GatewayVerification,
    PaymentGateway,
)


class ManualGateway(PaymentGateway):
    """Cash-on-visit (and every off-gateway method). Booking is immediately final.

    The anti-fraud invariant still holds: for manual methods the "verification"
    is the transaction literally not happening in a gateway — the session is
    marked paid on completion of the visit, and this path is only used for the
    legacy immediate-completion behaviour (cash / card / third-party mocks).
    """

    name = "manual"

    async def initiate(self, db, payment, payload: dict) -> GatewayInitiation:
        return GatewayInitiation(type="manual")

    async def verify(self, db, payment, params: dict) -> GatewayVerification:
        return GatewayVerification(COMPLETED, ref="CASH")