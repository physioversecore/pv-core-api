import json

from prisma import Prisma


async def get_setting(db: Prisma, key: str):
    return await db.setting.find_unique(where={"key": key})


async def upsert_setting(db: Prisma, key: str, value: dict):
    return await db.setting.upsert(
        where={"key": key},
        data={
            "create": {"key": key, "jsonValue": json.dumps(value)},
            "update": {"jsonValue": json.dumps(value)},
        },
    )
