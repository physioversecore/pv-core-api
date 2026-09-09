from .esewa import EsewaGateway
from .gateway import GATEWAY_METHODS, PaymentGateway, normalize_method
from .khalti import KhaltiGateway
from .manual import ManualGateway

_GATEWAYS: dict[str, PaymentGateway] = {
    "esewa": EsewaGateway(),
    "khalti": KhaltiGateway(),
}


def get_gateway(method: str) -> PaymentGateway:
    """Return the gateway for a payment method.

    Every non-gateway method (cash, card, third-party mocks, unknown strings)
    resolves to the manual gateway so the booking flow keeps working until a
    method is wired to a real rail.
    """
    m = normalize_method(method)
    if m in GATEWAY_METHODS and m in _GATEWAYS:
        return _GATEWAYS[m]
    return ManualGateway()


async def shutdown_gateway_clients():
    """No persistent clients to close today (httpx clients are per-request)."""