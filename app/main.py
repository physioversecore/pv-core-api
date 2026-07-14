from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import db

from app.routers import (
    admin_router,
    auth_router,
    cart_router,
    patients_router,
    payments_router,
    products_router,
    reports_router,
    reviews_router,
    sessions_router,
    therapists_router,
    uploads_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.disconnect()


app = FastAPI(
    title="Sahayatri Physio API",
    description="Backend API for the Sahayatri Physiotherapy platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(patients_router, prefix="/api/v1")
app.include_router(therapists_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(cart_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(reviews_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
