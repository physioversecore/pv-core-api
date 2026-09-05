# AGENTS.md — PVC API (Sahayatri Physio)

## Stack

Python 3.13 · FastAPI (async) · Prisma ORM (Python client) · PostgreSQL 16 · Redis 7 · uv package manager

## Setup

```sh
uv sync                         # install deps (requires .venv)
uv run prisma generate          # generate Prisma client (run after any schema change)
uv run prisma db push           # push schema to DB (dev only)
cp .env.example .env            # then edit DATABASE_URL + SECRET_KEY
uv run python main.py           # dev server on :8000
```

Or with Docker (starts Postgres + API, auto-pushes schema):
```sh
docker compose up --build       # dev with hot reload
```

## Prisma workflow

After editing `prisma/schema.prisma`, always run both:
```sh
uv run prisma generate
uv run prisma db push
```
Schema changes are NOT auto-applied on startup (except in Docker, which runs `db push` via entrypoint).

## Testing

```sh
uv run pytest                   # run all tests
uv run pytest test/test_auth.py # run single file
uv run pytest -k "login"        # run by name pattern
```

- pytest + pytest-asyncio (asyncio_mode = "auto" in pyproject.toml)
- Tests are **fully mocked** — no database required. `test/conftest.py` builds a fake FastAPI app with `MagicMock` DB and injects it via dependency overrides.
- Fixtures: `client` (unauthenticated), `patient_client`, `therapist_client`, `admin_client`
- If you add a new router, register it in `test/conftest.py` `_test_app` (it mirrors `app/main.py`)

No linter, formatter, or type checker is configured.

## Architecture

Three-layer: **routers → services → Prisma**

- `app/routers/` — HTTP concerns (parsing, validation, status codes). Delegate all DB logic to services.
- `app/services/` — Business logic + Prisma queries. No HTTP awareness.
- `app/models/` — Pure Pydantic request/response schemas. No DB or HTTP logic.
- `app/deps.py` — Shared dependencies: `get_current_user`, `get_admin_user`, `pagination_params`, `get_or_404`
- `app/database.py` — Prisma client singleton (`db`)
- `app/__init__.py` — Re-exports all public symbols. New consumers should `from app import X`.

### Registered Routers (15 total)

| Router | Tag | Prefix | Purpose |
|---|---|---|---|
| `auth_router` | Auth | `/api/v1/auth` | Send OTP, verify OTP, signup (requires prior verification), login, profile, change-password, logout |
| `patients_router` | Patients | `/api/v1/patients` | Patient dashboard, profile, referral, my-patients |
| `therapists_router` | Therapists | `/api/v1/therapists` | Therapist CRUD, slots, dashboard, profile |
| `earnings_router` | Earnings | `/api/v1/therapist` | Therapist earnings, payouts, transactions |
| `sessions_router` | Sessions | `/api/v1/sessions` | Session CRUD, reschedule |
| `products_router` | Products | `/api/v1/products` | Product catalog (admin CRUD) |
| `cart_router` | Cart | `/api/v1/cart` | Cart CRUD (patient only) |
| `payments_router` | Payments | `/api/v1/payments` | Payments, booking+payment flow |
| `admin_router` | Admin | `/api/v1/admin` | Users, therapists, patients, complaints, service areas, performance, verifications, refunds, activity log |
| `admin_extras_router` | Admin Extras | `/api/v1/admin` | Payments, payouts, notifications, team, leaves, incidents, analytics |
| `reports_router` | Reports | `/api/v1/reports` | Patient reports with file uploads |
| `uploads_router` | Uploads | `/api/v1/uploads` | Serve uploaded files |
| `reviews_router` | Reviews | `/api/v1/reviews` | Patient reviews and ratings |
| `settings_router` | Settings | `/api/v1/settings` | Design tokens, currencies, payment methods |
| `availability_router` | Availability | `/api/v1/availability` | Therapist availability (24+ endpoints) |

## Key conventions

- All API routes live under `/api/v1/`
- Auth via `HTTPBearer` token (JWT). Use `Depends(get_current_user)` or `Depends(get_admin_user)`.
- `get_or_404(db, "modelName", id)` — generic existence check for any Prisma model
- `pagination_params` — returns `{"skip": int, "limit": int}` from query params (defaults 0, 100; max 200)
- IDs are Prisma `cuid()` strings, not integers
- When adding a new domain (router + service + model), also add exports in `app/__init__.py` and the table mock in `test/conftest.py`
- Report file uploads use multipart/form-data, stored in `Upload/Reports/{patientId}/`
- Therapist media uploads stored in `Upload/Therapists/{therapistId}/`
- Working hours are stored in the `Setting` table with a `wh_{userId}` key pattern
- **Email provider**: Abstract `EmailProvider` base in `app/services/email/base.py`. `get_email_provider()` returns `SMTPEmailProvider` when `SMTP_USER` + `SMTP_PASSWORD` are set, otherwise falls back to `LogEmailProvider` (logs OTP codes to console). No code changes needed to switch — just set env vars and restart.
- **OTP flow**: `app/services/otp.py` generates 6-digit code, stores in `EmailVerification` table, sends via email provider. `send_otp()` invalidates previous unused codes. `verify_otp()` checks code, expiry, and max attempts. Signup endpoint verifies a prior successful OTP before creating the account.
- **SMTP config**: Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_NAME`, `SMTP_FROM_EMAIL` in `.env`. For Gmail, use an App Password (not regular password).

### Session statuses

`SCHEDULED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `RESCHEDULE_REQUESTED`, `DECLINE_REQUESTED`

### Session enrichment

Sessions returned by the API include `therapistName`, `patientName`, `patientPhone` via `_enrich_session()`.

### Slot uniqueness (anti double-booking)

Two patients can never book the same time slot of the same therapist. Enforced at three layers:

1. **Application check** — `create_session()` calls `is_slot_booked()` (`app/services/session.py`) before inserting, rejecting if an active (`SCHEDULED`/`IN_PROGRESS`) session already exists for `therapistId` + `date` + `time`. It raises `ValueError("CONFLICT")`.
2. **Router mapping** — both `POST /sessions` and `POST /payments/process` translate `ValueError("CONFLICT")` into **HTTP 409** with `"That time slot was just booked — please choose another."` (family-member errors remain 400).
3. **DB constraint** — a **unique index** `Session_therapistId_date_time_key` on `(therapistId, date, time)` (migration `20260901000000_session_slot_unique`) makes the guarantee race-safe at the database level; cancelled sessions are hard-deleted so the slot frees up.

`reschedule_session()` applies the same conflict check on the target slot (returns `"CONFLICT"` → 409).

## Prisma models (20+)

| Model | Purpose |
|---|---|
| `User` | Patients, therapists, admins (role enum) |
| `PatientProfile` | Extended patient profile (address, history, gender, notifications) |
| `Therapist` | Therapist profiles (linked to User) |
| `Verification` | Therapist document verification records |
| `Product` | Equipment, medicine, nutrition catalog |
| `Session` | Booked therapy sessions |
| `Review` | Patient reviews (unique per session) |
| `Report` | Patient reports with optional file attachments |
| `Payment` | Payment records (sessions + product purchases) |
| `CartItem` | Shopping cart items |
| `Setting` | Key-value store (design tokens, currencies, working hours) |
| `AvailabilitySlot` | Therapist time slots (unique per therapist+date+time) |
| `RecurringPattern` | Therapist recurring availability patterns |
| `AvailabilityBlock` | Therapist block-time-off records |
| `AuditLogEntry` | Availability change audit trail |
| `ScheduleBlockRequest` | Therapist requests for admin-approved time blocks |
| `Complaint` | Complaint/dispute records |
| `Refund` | Refund requests and tracking |
| `ServiceArea` | Geographic service areas |
| `TherapistServiceArea` | M2M linking therapists to service areas |
| `ActivityLog` | Admin activity audit trail |
| `EmailVerification` | OTP codes for email verification (email, code, purpose, expiresAt, used, attempts) |

### Enums

`Role` (PATIENT/THERAPIST/ADMIN), `UserStatus` (PENDING/APPROVED/REJECTED), `SessionStatus`, `SessionType` (HOME_VISIT/CLINIC), `ProductCategory` (EQUIPMENT/MEDICINE/NUTRITION), `CartItemType` (BUY/RENT/MEDICINE/NUTRITION), `CaseSource`, `RefundReason`, `RefundStatus`

## Seed scripts

Run in order (dependency-aware):
```sh
uv run scripts/seed-all.py       # runs all in correct order
uv run scripts/seed-users.py     # or run individually
```

All seed scripts (12 total):
- `seed-all.py` — orchestrator, runs all others
- `seed-users.py` — 14 users (3 patients, 1 admin, 8 therapists)
- `seed-therapists.py` — therapist profiles
- `seed-products.py` — product catalog
- `seed-sessions.py` — sample sessions
- `seed-reports.py` — patient reports
- `seed-reviews.py` — patient reviews
- `seed-therapist-dashboard.py` — dashboard data
- `seed-schedule.py` — availability slots
- `seed-settings.py` — design tokens, currencies, payment methods
- `seed-referral-codes.py` — referral codes
- `seed-patient-profiles.py` — patient profiles
- `seed-refunds.py` — refund records

Docker prod entrypoint runs `seed-all.py` automatically.

## Gotchas

- `docker-compose.yml` DB name is `sahayatri_physio` but `.env.example` DATABASE_URL uses `physioversecore` — they differ. Docker overrides via `environment` block.
- Test app (`conftest.py`) doesn't register `availability_router`, `settings_router`, `uploads_router`, `earnings_router`, or `admin_extras_router`. Tests for those routes won't work without adding them.
- Integration tests (`test/test_otp_integration.py`) require the live server running at port 9292. Run with `uv run python -m test.test_otp_integration`.
- `.gitignore` excludes `AGENTS.md` — this file is local-only, not committed.
- `bcrypt` is pinned `<4.1` due to passlib compatibility.
- CORS is wide open (`allow_origins=["*"]`) — fine for dev, restrict for production.
- Docker dev uses `prisma db push` (no migrations); prod uses `prisma migrate deploy`.
- `Upload/` directory is excluded from git via `.gitignore`.
- No linter, formatter, or type checker is configured.
