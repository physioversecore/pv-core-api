# Sahayatri Physio API

Backend API for the Sahayatri Physiotherapy platform. Built with **Python 3.13**, **FastAPI**, and **Prisma ORM** (PostgreSQL). Supports Patients, Therapists, and Admin roles with session booking, product shop, cart, payments, availability management, reporting, and comprehensive admin tools.

## Features

- JWT-based authentication (signup, login, role-based access)
- Therapist management (profiles, listings, approvals, verification)
- Therapist self-signup with document uploads (NMC license + certification) feeding admin verification — therapists receive a JWT on signup so the frontend can redirect them to the onboarding flow to complete their profile
- Session booking (home visit / clinic, scheduling, reschedule, status tracking)
- Therapist availability (working hours, slots, recurring patterns, block time off, audit log, block requests)
- Product shop (equipment, medicine, nutrition — buy or rent)
- Shopping cart with rental day calculation and delivery fee logic
- Payment tracking and booking+payment combo flow
- Patient progress reports with file uploads
- Reviews and ratings
- Complaints with up to 3 evidence attachments per filing (session-based upload + authenticated serving) and an admin "new complaints" badge endpoint (`GET /admin/complaints/new-count?since=`)
- Admin dashboard (manage users, therapists, sessions, payments, refunds, complaints, service areas, performance, safety incidents, notifications, analytics, team, activity log, leaves)
- Admin document verification with persisted rejection reasons and account verified/rejected emails
- Non-blocking transactional email (OTP, application received, account verified, application rejected) via FastAPI `BackgroundTasks`
- Distributed rate limiting (Redis-backed Sliding Window Counter with atomic Lua scripts)
- Auto-generated Swagger docs & ReDoc

---

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.13 |
| Framework | FastAPI (async) |
| ORM | Prisma (Python client) |
| Database | PostgreSQL 16 |
| Cache/Rate Limiting | Redis 7 |
| Auth | JWT (python-jose) + bcrypt |
| Package mgr | uv (Astral) |
| Validation | Pydantic v2 |
| Testing | pytest + pytest-asyncio (fully mocked, no DB needed) |

---

## Prerequisites

- Python 3.13 (see `.python-version`)
- [uv](https://docs.astral.sh/uv/) — install via `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`
- PostgreSQL 16 running locally (or use Docker — see below)

---

## Quick Start (Local)

### 1. Setup

```sh
uv python pin 3.13
uv venv
source .venv/bin/activate
uv sync
```

### 2. Configure environment

```sh
cp .env.example .env
# Edit .env with your database URL and a secure secret key
```

### 3. Generate Prisma client & push schema

```sh
uv run prisma generate
uv run prisma db push
```

### 4. Run the server

```sh
uv run python main.py
```

Server starts at **http://localhost:8000** with hot reload enabled.

---

## Docker (Recommended)

### Development

```sh
docker compose up --build
```

- Starts PostgreSQL + API with hot reload
- Source code is mounted so changes reflect immediately
- Schema auto-pushed on startup
- App at **http://localhost:8000**

### Production

```sh
export POSTGRES_PASSWORD=your-secure-password
docker compose -f docker-compose.prod.yml up --build -d
```

- Multi-stage build for small image size
- No source mount — fully self-contained
- Auto-restart on failure
- Runs migrations + seeds on startup via entrypoint

### Stop

```sh
docker compose down          # dev
docker compose -f docker-compose.prod.yml down   # prod
# Add -v to also remove volume: docker compose down -v
```

---

## API Documentation

| Tool | URL |
|---|---|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health check | `GET /health` |

All endpoints are under `/api/v1/`.

---

## Project Structure

```
main.py                  # CLI entrypoint (uvicorn, reload via env var)
app/
  __init__.py            # Re-exports all public symbols
  main.py                # FastAPI app, CORS, lifespan, router includes, rate limit middleware
  config.py              # pydantic-settings (reads .env) — includes Redis & rate limit config
  database.py            # Prisma client singleton
  deps.py                # JWT auth deps, pagination, get_or_404
  exceptions.py          # Global exception handlers
  logging_config.py      # Structured (JSON) + Dev (colored) formatters
  middleware.py           # RequestIDMiddleware (X-Request-ID, X-Response-Time)
  models/                # Pydantic request/response schemas (18 files)
  routers/               # API route handlers (15 files)
  services/              # Business logic layer (19 files)
  services/email/        # Email system: provider base + SMTP + log fallback + fire-and-forget dispatch + notifications
  templates/             # Jinja2 email templates (OTP, application received, account verified, application rejected)
  rate_limit/            # Distributed rate limiting system (12 files)
    config.py            # Rate limiting rules & configuration
    storage.py           # Redis + Memory storage backends
    algorithms.py        # Sliding Window Counter + Token Bucket
    lua_scripts.py       # Atomic Redis Lua scripts
    middleware.py         # Global ASGI middleware
    dependencies.py      # Route-level FastAPI dependency
    access_list.py       # Whitelist/blacklist with TTL
    metrics.py           # Prometheus-compatible metrics
prisma/
  schema.prisma          # Prisma ORM schema (20+ models, 471 lines)
  migrations/            # 17 migration directories
scripts/                 # Seed scripts (12 total)
test/                    # Test suite (14 files, fully mocked)
Dockerfile               # Production multi-stage build
Dockerfile.dev           # Development image with hot reload
docker-compose.yml       # Dev: API + PostgreSQL
docker-compose.prod.yml  # Production: API + PostgreSQL + Redis
```

---

## API Overview

### Authentication
| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/api/v1/auth/send-otp` | Send 6-digit OTP to email | Public |
| POST | `/api/v1/auth/verify-otp` | Verify OTP code | Public |
| POST | `/api/v1/auth/signup` | Register new user (requires prior email verification) | Public |
| POST | `/api/v1/auth/login` | Login, returns JWT | Public |
| GET | `/api/v1/auth/me` | Get current user profile | Authenticated |
| PUT | `/api/v1/auth/me` | Update profile | Authenticated |
| POST | `/api/v1/auth/change-password` | Change password | Authenticated |
| POST | `/api/v1/auth/logout` | Logout | Public |

### Therapists
| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/v1/therapists` | List therapists (verified/APPROVED only) | Public |
| GET | `/api/v1/therapists/me` | My therapist profile | Therapist |
| GET | `/api/v1/therapists/me/dashboard` | Therapist dashboard stats | Therapist |
| POST | `/api/v1/therapists` | Create therapist profile | Therapist |
| GET | `/api/v1/therapists/{id}` | Get therapist by ID (unverified hidden — 404 unless owner/Admin) | Public* |
| PUT | `/api/v1/therapists/{id}` | Update therapist profile | Owner/Admin |
| DELETE | `/api/v1/therapists/{id}` | Delete therapist | Owner/Admin |
| GET | `/api/v1/therapists/{id}/slots` | Get therapist slots | Authenticated |

\* Public listings surface **verified therapists only**: the list filters on `user.status == APPROVED` (excludes under-review/suspended), and fetching an unverified therapist by ID returns 404 unless the caller is the owner or an Admin.

### Sessions (Bookings)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/api/v1/sessions` | Book a session | Patient |
| GET | `/api/v1/sessions` | List sessions | Patient/Therapist/Admin |
| GET | `/api/v1/sessions/{id}` | Get session details | Authenticated |
| PUT | `/api/v1/sessions/{id}` | Update session | Patient/Therapist/Admin |
| DELETE | `/api/v1/sessions/{id}` | Cancel session | Patient/Admin |
| PATCH | `/api/v1/sessions/{id}/reschedule` | Reschedule session | Patient |

### Shop (Products)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/v1/products` | List products (filter by category) | Public |
| GET | `/api/v1/products/{id}` | Get product details | Public |
| POST | `/api/v1/products` | Create product | Admin |
| PUT | `/api/v1/products/{id}` | Update product | Admin |
| DELETE | `/api/v1/products/{id}` | Delete product | Admin |

### Cart
| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/v1/cart` | Get my cart with totals | Patient |
| POST | `/api/v1/cart` | Add item to cart | Patient |
| PUT | `/api/v1/cart/{item_id}` | Update cart item | Patient |
| DELETE | `/api/v1/cart/{item_id}` | Remove cart item | Patient |
| DELETE | `/api/v1/cart` | Clear entire cart | Patient |

### Payments
| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/api/v1/payments/process` | Booking + payment combo | Patient |
| POST | `/api/v1/payments` | Create payment | Authenticated |
| GET | `/api/v1/payments` | List payments | User (own) / Admin (all) |
| GET | `/api/v1/payments/{id}` | Get payment details | Authenticated |
| PUT | `/api/v1/payments/{id}/status` | Update payment status | Admin |

### Reports
| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/api/v1/reports` | Create progress report (multipart) | Therapist/Admin |
| GET | `/api/v1/reports` | List reports | Patient (own) / Therapist/Admin |
| GET | `/api/v1/reports/{id}` | Get report details | Authenticated |
| PUT | `/api/v1/reports/{id}` | Update report | Therapist/Admin |
| DELETE | `/api/v1/reports/{id}` | Delete report | Therapist/Admin |

### Reviews
| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/v1/reviews/therapists-to-rate` | Therapists awaiting review | Patient |
| POST | `/api/v1/reviews` | Submit a review | Patient |
| GET | `/api/v1/reviews` | List reviews | Authenticated |

### Availability (24+ endpoints)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET/PUT | `/api/v1/availability/working-hours` | Get/set working hours | Therapist |
| POST | `/api/v1/availability/apply-schedule` | Apply schedule | Therapist |
| GET | `/api/v1/availability` | Monthly availability grid | Therapist |
| POST | `/api/v1/availability/slot` | Toggle single slot | Therapist |
| POST | `/api/v1/availability/bulk` | Bulk toggle slots | Therapist |
| POST | `/api/v1/availability/recurring` | Create recurring pattern | Therapist |
| POST | `/api/v1/availability/open-month` | Open entire month | Therapist |
| POST | `/api/v1/availability/block-date` | Block a date | Therapist |
| POST | `/api/v1/availability/generate` | Generate slots | Therapist |
| POST | `/api/v1/availability/block-range` | Block date range | Therapist |
| POST | `/api/v1/availability/unblock` | Unblock dates | Therapist |
| GET | `/api/v1/availability/slots` | Get available slots | Authenticated |
| GET/POST | `/api/v1/availability/audit-log` | View/add audit entries | Therapist |
| POST | `/api/v1/availability/block-request` | Request admin-approved block | Therapist |
| GET | `/api/v1/availability/block-requests` | List block requests | Therapist/Admin |
| PUT | `/api/v1/availability/block-requests/{id}/approve` | Approve block request | Admin |
| PUT | `/api/v1/availability/block-requests/{id}/reject` | Reject block request | Admin |

### Patients
| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/v1/patients/me/profile` | Patient profile | Authenticated |
| PUT | `/api/v1/patients/me/profile` | Update patient profile | Authenticated |
| GET | `/api/v1/patients/me/dashboard` | Patient dashboard stats | Authenticated |
| GET | `/api/v1/patients/me/referral` | Referral code | Authenticated |
| GET | `/api/v1/patients/my-patients` | Therapist's patients | Therapist |

### Earnings
| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/v1/therapist/earnings/transactions` | Transaction history | Therapist |
| GET | `/api/v1/therapist/earnings/payouts` | Payout history | Therapist |

### Admin (60+ endpoints)
Includes: users CRUD, therapist management, patient management, dashboard stats, bookings (incl. `GET /bookings/new-count?since=` for the sidebar badge), complaints (CRUD, assign, `GET /complaints/new-count?since=`), service areas, performance, verifications, refunds, activity log, payments, payouts, notifications, team, leaves, incidents, analytics (stats, bookings-by-zone, cancellation-rate, revenue-trend).

### Settings
| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/v1/settings/design-tokens` | Get design tokens | Public |
| PUT | `/api/v1/settings/design-tokens` | Update design tokens | Admin |
| GET | `/api/v1/settings/currencies` | Get currencies | Public |
| PUT | `/api/v1/settings/currencies` | Update currencies | Admin |
| GET | `/api/v1/settings/payment-methods` | Get payment methods | Public |
| PUT | `/api/v1/settings/payment-methods` | Update payment methods | Admin |

### Uploads
| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/api/v1/uploads/therapist-application` | Upload verification docs before signup (returns relative URLs to embed in signup payload) | Public |
| GET | `/api/v1/uploads/applications/{session}/{filename}` | Serve a signup document | Authenticated |
| POST | `/api/v1/uploads/complaint-evidence` | Upload complaint evidence files before filing (session key; returns real URLs to embed in the complaint payload) | Public |
| GET | `/api/v1/uploads/evidence/{session}/{filename}` | Serve complaint evidence | Authenticated |
| GET | `/api/v1/uploads/{patient_id}/{filename}` | Download report file | Token-authenticated |
| GET | `/api/v1/uploads/therapists/{id}/{filename}` | Download therapist media | Authenticated |
| POST | `/api/v1/uploads/therapists/{id}` | Upload therapist media | Therapist/Admin |

### Health
| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/health` | Health check (DB + Redis) | Public |
| GET | `/live` | Liveness probe | Public |
| GET | `/ready` | Readiness probe (DB) | Public |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/physioversecore` | PostgreSQL connection string |
| `SECRET_KEY` | `super-secret-key-change-in-production` | JWT signing secret |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token expiry in minutes (24h) |
| `BACKEND_PORT` | `8000` | Server port |
| `UVICORN_RELOAD` | `true` | Enable/disable hot reload |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins (JSON array) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `RATE_LIMIT_ENABLED` | `true` | Enable/disable rate limiting |
| `RATE_LIMIT_DEFAULT_LIMIT` | `100` | Default requests per window |
| `RATE_LIMIT_DEFAULT_WINDOW` | `60` | Default window size in seconds |
| `RATE_LIMIT_STORAGE_BACKEND` | `redis` | Storage backend (`redis` or `memory`) |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server host |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USER` | (empty) | SMTP username/email (empty = log OTP to console) |
| `SMTP_PASSWORD` | (empty) | SMTP password (empty = log OTP to console) |
| `SMTP_FROM_NAME` | `Sahayatri Physio` | Sender display name |
| `SMTP_FROM_EMAIL` | `noreply@sahayatri.np` | Sender email address |
| `SMTP_USE_TLS` | `true` | Enable STARTTLS |
| `OTP_EXPIRE_MINUTES` | `5` | OTP code expiry in minutes |
| `OTP_LENGTH` | `6` | OTP code digit count |
| `OTP_MAX_ATTEMPTS` | `5` | Max verification attempts before code expires |
| `POSTGRES_PASSWORD` | `postgres` | Docker Postgres password (prod only) |

---

## Testing

```sh
uv run pytest                   # run all tests
uv run pytest test/test_auth.py # run single file
uv run pytest -k "login"        # run by name pattern
uv run python -m test.test_otp_integration  # integration tests (requires live server at :9292)
```

Tests are **fully mocked** — no database required. `test/conftest.py` builds a fake FastAPI app with `MagicMock` DB. Fixtures: `client`, `patient_client`, `therapist_client`, `admin_client`.

Integration tests (`test/test_otp_integration.py`) run against the live server and verify the full OTP → signup → login flow end-to-end.

---

## Managing Dependencies

```sh
uv add <package>           # add a new dependency
uv remove <package>        # remove a dependency
uv sync                    # sync lockfile after changes
```

All dependencies are tracked in `pyproject.toml` and `uv.lock`.

---

## Database Schema (Prisma)

20+ models in `prisma/schema.prisma` with 17 migrations. Key models: `User`, `Therapist`, `PatientProfile`, `Verification`, `Product`, `Session`, `Review`, `Report`, `Payment`, `CartItem`, `Setting`, `AvailabilitySlot`, `RecurringPattern`, `AvailabilityBlock`, `AuditLogEntry`, `ScheduleBlockRequest`, `Complaint`, `Refund`, `ServiceArea`, `ActivityLog`, `EmailVerification`.

`Therapist.licenseNumber` and `Verification.documentUrl`/`fileName`/`fileSize` were added (migration `20260801000000_add_verification_documents`) so self-signup therapists' uploaded documents feed the admin verification review. `Verification.note` (admin rejection reason, max 2000 chars) was added later and pushed to the dev DB via `prisma db push`. `Complaint.evidenceUrls` (comma-separated `/api/v1/uploads/evidence/{session}/{filename}` URLs) stores complaint evidence attachments.

All email sends are fire-and-forget via `app/services/email/dispatch.py` scheduled on FastAPI `BackgroundTasks`: OTP codes, the therapist "application received" email on signup, and the account verified/rejected emails on admin verification. Admin approval (`Verified`) emails the therapist; rejection (`Rejected`) persists the `note` reason, includes it in the email, and returns it to the frontend.

After modifying `prisma/schema.prisma`:

```sh
uv run prisma generate     # regenerate Python client
uv run prisma db push       # sync schema to database (dev only)
```

For production migrations, use `prisma migrate dev` to create migration files, then `prisma migrate deploy` in production.
