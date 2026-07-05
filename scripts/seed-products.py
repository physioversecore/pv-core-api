import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

PRODUCTS = [
    # Equipment
    {"name": "Standard Wheelchair",         "category": "EQUIPMENT", "price": 18000, "rentPerDay": 150, "inStock": 1, "emoji": "♿", "description": "Foldable, lightweight, 100kg capacity."},
    {"name": "Adjustable Crutches (Pair)",  "category": "EQUIPMENT", "price": 2200,  "rentPerDay": 40,  "inStock": 1, "emoji": "🩼", "description": "Aluminum, height adjustable."},
    {"name": "TENS Therapy Unit",           "category": "EQUIPMENT", "price": 4500,  "rentPerDay": 80,  "inStock": 1, "emoji": "⚡",  "description": "Dual-channel pain relief device."},
    {"name": "Hot & Cold Therapy Pack",     "category": "EQUIPMENT", "price": 850,   "rentPerDay": 20,  "inStock": 1, "emoji": "🧊",  "description": "Reusable gel pack with strap."},
    {"name": "Knee Support Brace",          "category": "EQUIPMENT", "price": 1600,  "rentPerDay": 0,   "inStock": 1, "emoji": "🦵",  "description": "Post-op stabilizing brace."},
    {"name": "Walker with Wheels",          "category": "EQUIPMENT", "price": 6500,  "rentPerDay": 60,  "inStock": 0, "emoji": "🚶",  "description": "Senior-friendly mobility walker."},
    # Medicine
    {"name": "Ibuprofen 400mg (10 tabs)",   "category": "MEDICINE",  "price": 120,   "inStock": 1, "emoji": "💊", "description": "Pain & inflammation relief."},
    {"name": "Diclofenac Gel 30g",          "category": "MEDICINE",  "price": 240,   "inStock": 1, "emoji": "🧴", "description": "Topical anti-inflammatory."},
    {"name": "Calcium + D3 (30 tabs)",      "category": "MEDICINE",  "price": 380,   "inStock": 1, "emoji": "🦴", "description": "Bone health supplement."},
    {"name": "Muscle Relaxant (10 tabs)",   "category": "MEDICINE",  "price": 280,   "inStock": 1, "emoji": "💊", "description": "Rx — uploaded by therapist."},
    # Nutrition
    {"name": "Whey Protein 1kg",            "category": "NUTRITION", "price": 3200,  "inStock": 1, "emoji": "🥤", "description": "Muscle recovery support."},
    {"name": "Collagen Peptides 250g",      "category": "NUTRITION", "price": 2400,  "inStock": 1, "emoji": "🍶", "description": "Joint & tissue repair."},
    {"name": "Omega-3 (60 caps)",           "category": "NUTRITION", "price": 1100,  "inStock": 1, "emoji": "🐟", "description": "Anti-inflammatory."},
    {"name": "Recovery Meal Plan (1 week)", "category": "NUTRITION", "price": 1800,  "inStock": 1, "emoji": "🍱", "description": "Nepali-style nutrition plan."},
]


async def main():
    db = Prisma(auto_register=True)
    await db.connect()

    for p in PRODUCTS:
        existing = await db.product.find_first(where={"name": p["name"]})
        if existing:
            print(f"SKIP  {p['name']} — already exists (id={existing.id})")
            continue

        product = await db.product.create(data=p)
        print(f"CREATED {p['name']} — id={product.id}, category={product.category}")

    await db.disconnect()
    print("\nProducts seeded.")


if __name__ == "__main__":
    asyncio.run(main())
