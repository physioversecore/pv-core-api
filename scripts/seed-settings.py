import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import db
from app.services.settings import get_setting, upsert_setting

CURRENCIES = [
    {"code": "NPR", "name": "Nepalese Rupee",    "flag": "\U0001f1f3\U0001f1f5", "symbol": "Rs.",  "rate": 1},
    {"code": "USD", "name": "US Dollar",          "flag": "\U0001f1fa\U0001f1f8", "symbol": "$",    "rate": 0.0075},
    {"code": "AUD", "name": "Australian Dollar",  "flag": "\U0001f1e6\U0001f1fa", "symbol": "A$",   "rate": 0.011},
    {"code": "EUR", "name": "Euro",               "flag": "\U0001f1ea\U0001f1fa", "symbol": "\u20ac", "rate": 0.0069},
    {"code": "GBP", "name": "British Pound",      "flag": "\U0001f1ec\U0001f1e7", "symbol": "\u00a3", "rate": 0.0059},
    {"code": "CAD", "name": "Canadian Dollar",    "flag": "\U0001f1e8\U0001f1e6", "symbol": "C$",   "rate": 0.01},
    {"code": "INR", "name": "Indian Rupee",       "flag": "\U0001f1ee\U0001f1f3", "symbol": "\u20b9", "rate": 0.63},
    {"code": "SGD", "name": "Singapore Dollar",   "flag": "\U0001f1f8\U0001f1ec", "symbol": "S$",   "rate": 0.01},
    {"code": "JPY", "name": "Japanese Yen",       "flag": "\U0001f1ef\U0001f1f5", "symbol": "\u00a5", "rate": 1.12},
    {"code": "AED", "name": "UAE Dirham",         "flag": "\U0001f1e6\U0001f1ea", "symbol": "\u062f.\u0625", "rate": 0.028},
]

PAYMENT_METHODS = [
    {"id": "esewa",      "label": "eSewa",        "icon": "\U0001f4b3", "type": "nepal",         "subtype": "Digital wallet"},
    {"id": "khalti",     "label": "Khalti",        "icon": "\U0001f4b3", "type": "nepal",         "subtype": "Digital wallet"},
    {"id": "connectips", "label": "ConnectIPS",    "icon": "\U0001f3e6", "type": "nepal",         "subtype": "Bank transfer"},
    {"id": "imepay",     "label": "IME Pay",       "icon": "\U0001f4b3", "type": "nepal",         "subtype": "Digital wallet"},
    {"id": "fonepay",    "label": "FonePay",       "icon": "\U0001f4f1", "type": "nepal",         "subtype": "QR/mobile"},
    {"id": "cash",       "label": "Cash",          "icon": "\U0001f4b5", "type": "nepal",         "subtype": "Pay on visit"},
    {"id": "card",       "label": "Card",          "icon": "\U0001f4b3", "type": "international", "subtype": "Credit/Debit"},
    {"id": "paypal",     "label": "PayPal",        "icon": "\U0001f3e7", "type": "international", "subtype": "Online wallet"},
    {"id": "googlepay",  "label": "Google Pay",    "icon": "\U0001f4f1", "type": "international", "subtype": "Mobile wallet"},
    {"id": "applepay",   "label": "Apple Pay",     "icon": "\U0001f34e", "type": "international", "subtype": "Mobile wallet"},
]


async def main():
    await db.connect()

    currencies_row = await get_setting(db, "currencies")
    if not currencies_row:
        await upsert_setting(db, "currencies", CURRENCIES)
        print(f"CREATED currencies — {len(CURRENCIES)} entries")
    else:
        print("SKIP  currencies — already exists")

    methods_row = await get_setting(db, "payment-methods")
    if not methods_row:
        await upsert_setting(db, "payment-methods", PAYMENT_METHODS)
        print(f"CREATED payment-methods — {len(PAYMENT_METHODS)} entries")
    else:
        print("SKIP  payment-methods — already exists")

    await db.disconnect()
    print("\nSettings seeded.")


if __name__ == "__main__":
    asyncio.run(main())
