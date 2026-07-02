from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import db
from app.routers import (
    admin,
    auth,
    cart,
    payments,
    products,
    reports,
    sessions,
    therapists,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.disconnect()


app = FastAPI(
    title="Sahayatri Physio API",
    description="Backend API for the Sahayatri Physiotherapy platform. Supports Patients, Therapists, and Admin roles with session booking, product shop, payments, and reporting.",
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

app.include_router(auth.router, prefix="/api/v1")
app.include_router(therapists.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(cart.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
