from prisma import Prisma

db = Prisma(auto_register=True)


async def get_db() -> Prisma:
    yield db
