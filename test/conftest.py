from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app import get_admin_user, get_current_user, get_db
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
async def _noop_lifespan(_app):
    yield


_test_app = FastAPI(lifespan=_noop_lifespan)
_test_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_test_app.include_router(auth_router, prefix="/api/v1")
_test_app.include_router(patients_router, prefix="/api/v1")
_test_app.include_router(therapists_router, prefix="/api/v1")
_test_app.include_router(sessions_router, prefix="/api/v1")
_test_app.include_router(products_router, prefix="/api/v1")
_test_app.include_router(cart_router, prefix="/api/v1")
_test_app.include_router(payments_router, prefix="/api/v1")
_test_app.include_router(admin_router, prefix="/api/v1")
_test_app.include_router(reports_router, prefix="/api/v1")
_test_app.include_router(reviews_router, prefix="/api/v1")
_test_app.include_router(uploads_router, prefix="/api/v1")


@_test_app.get("/health")
async def health():
    return {"status": "ok"}

NOW = datetime(2024, 6, 15, 10, 30, 0)

MOCK_PATIENT = SimpleNamespace(
    id="patient-1",
    name="Test Patient",
    email="patient@test.com",
    password="$2b$12$LJ3m4ys3Lk0TSwHlOR./YuVF4vj4G.hC3sVJfFJkVixRClvD1zBWe",
    role="PATIENT",
    city="Kathmandu",
    phone="9800000001",
    specialty=None,
    status="APPROVED",
    referralCode="SAHA-TEST1234",
    tokenVersion=0,
    createdAt=NOW,
    updatedAt=NOW,
)

MOCK_THERAPIST_USER = SimpleNamespace(
    id="therapist-user-1",
    name="Test Therapist",
    email="therapist@test.com",
    password="$2b$12$LJ3m4ys3Lk0TSwHlOR./YuVF4vj4G.hC3sVJfFJkVixRClvD1zBWe",
    role="THERAPIST",
    city="Kathmandu",
    phone="9800000002",
    specialty="Physiotherapy",
    status="APPROVED",
    referralCode=None,
    tokenVersion=0,
    createdAt=NOW,
    updatedAt=NOW,
)

MOCK_ADMIN = SimpleNamespace(
    id="admin-1",
    name="Test Admin",
    email="admin@test.com",
    password="$2b$12$LJ3m4ys3Lk0TSwHlOR./YuVF4vj4G.hC3sVJfFJkVixRClvD1zBWe",
    role="ADMIN",
    city=None,
    phone=None,
    specialty=None,
    status="APPROVED",
    referralCode=None,
    tokenVersion=0,
    createdAt=NOW,
    updatedAt=NOW,
)

MOCK_THERAPIST_PROFILE = SimpleNamespace(
    id="therapist-1",
    userId="therapist-user-1",
    name="Dr. Therapist",
    specialty="Physiotherapy",
    city="Kathmandu",
    gender="Male",
    rating=4.5,
    reviews=10,
    price=1500.0,
    experience=5,
    bio="Experienced physiotherapist",
    createdAt=NOW,
    updatedAt=NOW,
)

MOCK_SESSION = SimpleNamespace(
    id="session-1",
    therapistId="therapist-1",
    patientId="patient-1",
    date=NOW,
    time="10:00",
    type="HOME_VISIT",
    status="SCHEDULED",
    address="Test Address",
    fee=1500.0,
    notes=None,
    createdAt=NOW,
    updatedAt=NOW,
)

MOCK_PRODUCT = SimpleNamespace(
    id="product-1",
    name="Test Product",
    category="EQUIPMENT",
    price=500.0,
    rentPerDay=50.0,
    inStock=10,
    emoji="🔧",
    description="Test description",
    imageUrl="http://example.com/img.jpg",
    createdAt=NOW,
    updatedAt=NOW,
)

MOCK_CART_ITEM = SimpleNamespace(
    id="cart-1",
    userId="patient-1",
    productId="product-1",
    product=MOCK_PRODUCT,
    type="BUY",
    quantity=2,
    rentalDays=7,
    createdAt=NOW,
    updatedAt=NOW,
)

MOCK_PAYMENT = SimpleNamespace(
    id="payment-1",
    userId="patient-1",
    amount=1000.0,
    status="PENDING",
    method="CASH",
    sessionId=None,
    createdAt=NOW,
    updatedAt=NOW,
)

MOCK_REPORT = SimpleNamespace(
    id="report-1",
    patientId="patient-1",
    sessionId=None,
    title="Test Report",
    content="Report content",
    fileUrl=None,
    createdAt=NOW,
    updatedAt=NOW,
)

MOCK_COMPLETED_SESSION = SimpleNamespace(
    id="session-completed-1",
    therapistId="therapist-1",
    patientId="patient-1",
    date=NOW,
    time="10:00",
    type="HOME_VISIT",
    status="COMPLETED",
    address="Test Address",
    fee=1500.0,
    notes=None,
    createdAt=NOW,
    updatedAt=NOW,
    therapist=MOCK_THERAPIST_PROFILE,
    patient=MOCK_PATIENT,
    review=None,
)

MOCK_REVIEW = SimpleNamespace(
    id="review-1",
    sessionId="session-completed-1",
    patientId="patient-1",
    therapistId="therapist-1",
    rating=5,
    comment="Great therapist",
    createdAt=NOW,
    updatedAt=NOW,
    therapist=MOCK_THERAPIST_PROFILE,
    session=MOCK_COMPLETED_SESSION,
)

TABLES = ["user", "therapist", "session", "product", "cartitem", "payment", "report", "review", "emailverification", "verification", "activitylog", "refund", "complaint", "scheduleblockrequest", "servicearea", "availabilityslot", "recurringpattern", "availabilityblock", "auditlogentry", "adminnotification"]
METHODS = [
    "find_unique",
    "find_many",
    "find_first",
    "create",
    "update",
    "update_many",
    "delete",
    "delete_many",
    "count",
]


def _make_table_mock():
    tbl = MagicMock()
    for m in METHODS:
        setattr(tbl, m, AsyncMock())
    return tbl


@pytest.fixture
def mock_db():
    db = MagicMock()
    for t in TABLES:
        setattr(db, t, _make_table_mock())
    return db


@pytest.fixture
def client(mock_db):
    _test_app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(_test_app) as c:
        yield c
    _test_app.dependency_overrides.clear()


@pytest.fixture
def patient_client(client):
    _test_app.dependency_overrides[get_current_user] = lambda: MOCK_PATIENT
    yield client
    _test_app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def therapist_client(client):
    _test_app.dependency_overrides[get_current_user] = lambda: MOCK_THERAPIST_USER
    yield client
    _test_app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def admin_client(client):
    _test_app.dependency_overrides[get_current_user] = lambda: MOCK_ADMIN
    _test_app.dependency_overrides[get_admin_user] = lambda: MOCK_ADMIN
    yield client
    _test_app.dependency_overrides.pop(get_current_user, None)
    _test_app.dependency_overrides.pop(get_admin_user, None)
