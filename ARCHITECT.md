# PVC API — Architecture

## Overview

PVC API is the backend for the Sahayatri Physiotherapy platform. Built with **Python 3.13**, **FastAPI**, and **Prisma ORM** (PostgreSQL). Supports three user roles:

- **Patients** — Book sessions, shop products, track reports
- **Therapists** — Manage schedules/availability, submit reports, track earnings
- **Admins** — Approve therapists, manage users, oversee bookings/payments, handle complaints/refunds, manage service areas, performance reviews, safety incidents, analytics, and platform settings

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
| Testing | pytest + pytest-asyncio (fully mocked) |

---

## Project Structure

```
main.py                  # CLI entrypoint (uvicorn with hot reload)
app/
  __init__.py            # Re-exports all public symbols from submodules
  main.py                # FastAPI app, CORS, lifespan, router includes, rate limit middleware
  config.py              # pydantic-settings (reads .env) — includes Redis & rate limit config
  database.py            # Prisma client singleton
  deps.py                # Reusable deps: JWT auth, pagination, get_or_404
  exceptions.py          # Global exception handlers (HTTPException, Validation, JWT, Prisma)
  logging_config.py      # Structured (JSON) + Dev (colored) formatters
  middleware.py           # RequestIDMiddleware (X-Request-ID, X-Response-Time)
  models/                # Pydantic request/response schemas (18 files)
  routers/               # API route handlers (15 files)
  services/              # Business logic layer (19 files)
  services/email/        # Email provider system (abstract base + SMTP + log fallback)
  templates/             # Jinja2 email templates (OTP verification)
  rate_limit/            # Distributed rate limiting system (12 files)
    __init__.py          # Public API, init_rate_limiting()
    config.py            # RateLimitRule, RateLimitConfig, endpoint/role defaults
    storage.py           # Abstract RateLimitStorage + RedisStorage + MemoryStorage
    algorithms.py        # SlidingWindowCounter + TokenBucket behind RateLimiter ABC
    lua_scripts.py       # Atomic Redis Lua scripts for sliding window & token bucket
    middleware.py         # FastAPI BaseHTTPMiddleware (global rate limiting)
    dependencies.py      # FastAPI Depends() for route-level rate limiting
    access_list.py       # Whitelist/blacklist with TTL support
    metrics.py           # Thread-safe Prometheus-compatible metrics
    log.py               # Structured request logging
    exceptions.py        # RateLimitExceeded, RateLimitStorageError
prisma/
  schema.prisma          # Prisma schema (23 models, 509 lines)
  migrations/            # 17 migration directories
scripts/                 # Seed scripts (12 total)
test/                    # Test suite (14 files, fully mocked)
```

---

## Module Layer Rules

- **`app/__init__.py`** — Re-exports all public symbols from `models/`, `services/`, `routers/`, `deps.py`, `database.py`. Consumers always `from app import X`.
- **Routers** — Handle HTTP concerns (parsing, validation, status codes, response shapes). Delegate all DB/business logic to services.
- **Services** — Business logic and Prisma queries. No HTTP awareness.
- **Models** — Pure Pydantic request/response schemas. No DB or HTTP logic.

---

## Reusable Dependencies (`app/deps.py`)

| Dependency | Purpose |
|---|---|
| `get_current_user` | Decode JWT, return `User` or 401 |
| `get_admin_user` | Wraps `get_current_user`, checks `role == ADMIN` |
| `pagination_params` | Returns `{"skip": int, "limit": int}` from query params (defaults 0, 100; max 200) |
| `get_or_404(db, model, id)` | Generic find-or-404; works for any Prisma model |

### Rate Limiting Dependencies (`app/rate_limit/dependencies.py`)

| Dependency | Purpose |
|---|---|
| `rate_limit(limit, window)` | Route-level rate limit decorator (per-endpoint override) |
| `get_rate_limiter` | Returns the global `RateLimiter` singleton |

---

## API Endpoints

All endpoints under `/api/v1/`. See Swagger UI at `/docs` or ReDoc at `/redoc`.

### Auth
| Method | Path | Access |
|---|---|---|
| POST | `/auth/send-otp` | Public (sends 6-digit OTP to email) |
| POST | `/auth/verify-otp` | Public (verifies OTP code) |
| POST | `/auth/signup` | Public (requires prior email verification) |
| POST | `/auth/login` | Public |
| GET  | `/auth/me` | Authenticated |
| PUT  | `/auth/me` | Authenticated |
| POST | `/auth/change-password` | Authenticated |
| POST | `/auth/logout` | Public |

### Therapists
| Method | Path | Access |
|---|---|---|
| GET  | `/therapists` | Public |
| POST | `/therapists` | Therapist |
| GET  | `/therapists/me` | Therapist |
| GET  | `/therapists/me/dashboard` | Therapist |
| GET  | `/therapists/me/profile` | Therapist |
| PUT  | `/therapists/me/profile` | Therapist |
| GET  | `/therapists/{id}` | Public |
| PUT  | `/therapists/{id}` | Owner/Admin |
| DEL  | `/therapists/{id}` | Owner/Admin |
| GET  | `/therapists/{id}/slots` | Authenticated |

### Sessions
| Method | Path | Access |
|---|---|---|
| POST | `/sessions` | Patient |
| GET  | `/sessions` | Patient/Therapist/Admin |
| GET  | `/sessions/{id}` | Authenticated |
| PUT  | `/sessions/{id}` | Patient/Therapist/Admin |
| DEL  | `/sessions/{id}` | Patient/Admin |
| PATCH | `/sessions/{id}/reschedule` | Patient |

### Products
| Method | Path | Access |
|---|---|---|
| GET  | `/products` | Public |
| POST | `/products` | Admin |
| GET  | `/products/{id}` | Public |
| PUT  | `/products/{id}` | Admin |
| DEL  | `/products/{id}` | Admin |

### Cart
| Method | Path | Access |
|---|---|---|
| GET  | `/cart` | Patient |
| POST | `/cart` | Patient |
| PUT  | `/cart/{item_id}` | Patient |
| DEL  | `/cart/{item_id}` | Patient |
| DEL  | `/cart` | Patient (clear) |

### Payments
| Method | Path | Access |
|---|---|---|
| POST | `/payments/process` | Patient (booking+payment combo) |
| POST | `/payments` | Authenticated |
| GET  | `/payments` | User (own) / Admin (all) |
| GET  | `/payments/{id}` | Authenticated |
| PUT  | `/payments/{id}/status` | Admin |

### Reports
| Method | Path | Access |
|---|---|---|
| POST | `/reports` | Therapist/Admin (multipart) |
| GET  | `/reports` | Patient (own) / Therapist+Admin (by patient_id) |
| GET  | `/reports/therapist` | Therapist/Admin |
| GET  | `/reports/{id}` | Authenticated |
| PUT  | `/reports/{id}` | Therapist/Admin |
| DEL  | `/reports/{id}` | Therapist/Admin |

### Reviews
| Method | Path | Access |
|---|---|---|
| GET  | `/reviews/therapists-to-rate` | Patient |
| POST | `/reviews` | Patient |
| GET  | `/reviews` | Authenticated |

### Patients
| Method | Path | Access |
|---|---|---|
| GET  | `/patients/me/profile` | Authenticated |
| PUT  | `/patients/me/profile` | Authenticated |
| GET  | `/patients/me/dashboard` | Authenticated |
| GET  | `/patients/me/referral` | Authenticated |
| GET  | `/patients/my-patients` | Therapist |

### Earnings
| Method | Path | Access |
|---|---|---|
| GET  | `/therapist/earnings/transactions` | Therapist |
| GET  | `/therapist/earnings/payouts` | Therapist |

### Availability (24+ endpoints)
| Method | Path | Access |
|---|---|---|
| GET/PUT | `/availability/working-hours` | Therapist |
| POST | `/availability/apply-schedule` | Therapist |
| GET  | `/availability` | Therapist (monthly grid) |
| POST | `/availability/slot` | Therapist (toggle) |
| POST | `/availability/bulk` | Therapist (bulk toggle) |
| POST | `/availability/recurring` | Therapist |
| GET  | `/availability/recurring` | Therapist |
| DEL/PUT | `/availability/recurring/{id}` | Therapist |
| POST | `/availability/open-month` | Therapist |
| POST | `/availability/block-date` | Therapist |
| POST | `/availability/generate` | Therapist |
| POST | `/availability/block-range` | Therapist |
| POST | `/availability/unblock` | Therapist |
| GET  | `/availability/slots` | Authenticated |
| GET  | `/availability/working-days` | Therapist |
| GET/POST | `/availability/audit-log` | Therapist |
| DEL  | `/availability/audit-log/{id}` | Therapist |
| POST | `/availability/block-request` | Therapist |
| GET  | `/availability/block-requests` | Therapist/Admin |
| PUT  | `/availability/block-requests/{id}/approve` | Admin |
| PUT  | `/availability/block-requests/{id}/reject` | Admin |

### Admin (60+ endpoints across admin + admin_extras)
Includes: users CRUD, therapist management (list, create, approve, reject, suspend), patient management, dashboard stats/earnings/recent activity, bookings, complaints (CRUD, assign), service areas (CRUD, assign therapists), performance (list, detail, update, resolve, schedule review, remove), verifications (CRUD, suspend), refunds (CRUD, stats, manual cases, assign), activity log, payments management, payouts, notifications, team management, leaves, incidents (escalate/resolve), analytics (stats, bookings-by-zone, cancellation-rate, revenue-trend).

### Settings
| Method | Path | Access |
|---|---|---|
| GET  | `/settings/design-tokens` | Public |
| PUT  | `/settings/design-tokens` | Admin |
| GET  | `/settings/currencies` | Public |
| PUT  | `/settings/currencies` | Admin |
| GET  | `/settings/payment-methods` | Public |
| PUT  | `/settings/payment-methods` | Admin |

### Uploads
| Method | Path | Access |
|---|---|---|
| POST | `/uploads/therapist-application` | Public (pre-signup verification documents, `files` + `session` Form fields) |
| GET  | `/uploads/applications/{session}/{filename}` | Authenticated |
| GET  | `/uploads/{patient_id}/{filename}?token=...` | Token-authenticated |
| GET  | `/uploads/therapists/{id}/{filename}` | Authenticated |
| POST | `/uploads/therapists/{id}` | Therapist/Admin |

### Health
| Method | Path | Access |
|---|---|---|
| GET  | `/health` | Public (checks DB + Redis) |
| GET  | `/live` | Public (always ok) |
| GET  | `/ready` | Public (checks DB, 503 if down) |

---

## Database Schema (20+ models)

| Model | Purpose |
|---|---|
| `User` | Patients, therapists, admins (role enum: PATIENT/THERAPIST/ADMIN) |
| `PatientProfile` | Extended patient profile (address, history, gender, notifications) |
| `Therapist` | Therapist profiles (linked 1:1 to User, incl. `licenseNumber` from signup) |
| `Verification` | Therapist document verification records (`documentUrl`/`fileName`/`fileSize` from signup uploads) |
| `Product` | Equipment, medicine, nutrition catalog |
| `Session` | Booked therapy sessions with status tracking |
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

`Role` (PATIENT/THERAPIST/ADMIN), `UserStatus` (PENDING/APPROVED/REJECTED), `SessionStatus` (SCHEDULED/IN_PROGRESS/COMPLETED/CANCELLED/RESCHEDULE_REQUESTED/DECLINE_REQUESTED), `SessionType` (HOME_VISIT/CLINIC), `ProductCategory` (EQUIPMENT/MEDICINE/NUTRITION), `CartItemType` (BUY/RENT/MEDICINE/NUTRITION), `CaseSource` (PATIENT_SUBMITTED/THERAPIST_SUBMITTED/ADMIN_MANUAL), `RefundReason` (NO_SHOW/DOUBLE_CHARGE/SERVICE_QUALITY/CANCELLATION), `RefundStatus` (PENDING/APPROVED/DENIED)

---

## Email Provider Architecture

### Overview

Pluggable email system for sending OTP verification codes and future transactional emails. Designed for easy provider swapping without code changes.

### Components

```
app/services/email/
  base.py    # Abstract EmailProvider + get_email_provider() factory
  smtp.py    # SMTPEmailProvider (production — connects to SMTP server)
  log.py     # LogEmailProvider (dev — logs OTP codes to console)
app/services/otp.py      # OTP generate, send, verify logic
app/templates/otp_email.html  # Branded HTML email template (Jinja2)
```

### Provider Selection

`get_email_provider()` in `base.py` checks `SMTP_USER` and `SMTP_PASSWORD`:
- Both set → returns `SMTPEmailProvider` (sends real emails)
- Either empty → returns `LogEmailProvider` (logs OTP to console)

No code changes needed to switch — just set env vars and restart.

### OTP Flow

1. Frontend calls `POST /auth/send-otp` with `{email, name}`
2. `send_otp()` invalidates any previous unused OTP for that email+purpose
3. Generates 6-digit code, stores in `EmailVerification` table with expiry
4. Renders HTML email via Jinja2 template, sends via email provider
5. Frontend shows OTP input screen
6. User enters code → frontend calls `POST /auth/verify-otp`
7. `verify_otp()` checks: code match, not expired, attempts < max
8. On success, marks OTP as used
9. Frontend calls `POST /auth/signup` → backend checks for a verified OTP record before creating account

### SMTP Configuration

| Variable | Default | Description |
|---|---|---|
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server host |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USER` | (empty) | SMTP username (empty = log fallback) |
| `SMTP_PASSWORD` | (empty) | SMTP password (empty = log fallback) |
| `SMTP_FROM_NAME` | `Sahayatri Physio` | Sender display name |
| `SMTP_FROM_EMAIL` | `noreply@sahayatri.np` | Sender email address |
| `SMTP_USE_TLS` | `true` | Enable STARTTLS |
| `OTP_EXPIRE_MINUTES` | `5` | OTP code expiry |
| `OTP_LENGTH` | `6` | OTP digit count |
| `OTP_MAX_ATTEMPTS` | `5` | Max verification attempts |

For Gmail: generate an [App Password](https://myaccount.google.com/apppasswords) under Security → 2-Step Verification → App passwords.

---

## Key Design Decisions

1. **Three-layer architecture** — routers → services → Prisma. Services encapsulate business logic; routers handle HTTP.
2. **Role-based access** — JWT payload carries `sub` (user id); endpoints use `get_current_user` / `get_admin_user` dependencies.
3. **DRY dependencies** — `pagination_params` and `get_or_404` eliminate repeated pagination + existence-check boilerplate.
4. **`__init__.py` re-exports** — All public symbols are re-exported from `app/__init__.py`. Consumers always `from app import X`.
5. **Flat route structure** — `/{resource}` and `/{resource}/{id}` pattern; no nested sub-resources.
6. **Cart totals** — Computed in-memory: rental items use `price × qty × rentalDays`; delivery free above Rs 2,000, otherwise Rs 150.
7. **Session enrichment** — `_enrich_session()` adds `therapistName`, `patientName`, `patientPhone` to session responses.
8. **Distributed rate limiting** — Redis-backed Sliding Window Counter with atomic Lua scripts. Fail-open on Redis failure.
9. **Structured logging** — JSON format in production, colored console in development. Request IDs propagated through context vars.
10. **Pluggable email providers** — Abstract `EmailProvider` base with SMTP implementation. Auto-fallback to console logging when SMTP is unconfigured. OTP verification gates signup to prevent fake registrations.
11. **OTP verification before signup** — `EmailVerification` model stores codes with TTL and attempt limits. Signup endpoint requires a verified record before creating the user account.
12. **Pre-signup document uploads** — Therapists upload NMC license + certification *before* an account exists via the public `POST /uploads/therapist-application` (client-generated `session` key). Returned relative URLs are embedded in the signup payload; `create_therapist_signup()` (in `app/services/auth.py`) creates the `Therapist` profile (licenseNumber/fee/experience/bio) plus one `Verification` row per document (status `Pending review`, reportedBy `Self-signup`) so admin verification has real files + credentials to review. Documents are served to authenticated users via `GET /uploads/applications/{session}/{filename}` (path-traversal guarded).

---

## Rate Limiting Architecture

### Overview

Production-grade distributed rate limiting using the **Sliding Window Counter** algorithm backed by **Redis**. Prevents abuse while allowing legitimate burst traffic. Implemented as ASGI middleware (global) + optional route-level dependency.

### Algorithm: Sliding Window Counter

Maintains two counters per client+endpoint:
- `current_count` — requests in the current time window
- `previous_count` — requests in the previous time window

**Estimated count** = `(previous_count × weight) + current_count`

Where `weight` = percentage of the previous window that has elapsed into the current window. This eliminates the boundary burst problem of fixed-window counters.

### Redis Key Structure

```
rl:{identifier}:{endpoint}:{window_id}
```

- `identifier` — `user:{id}` (authenticated) or `ip:{address}` (anonymous)
- `endpoint` — request path (e.g., `/api/v1/sessions`)
- `window_id` — `unix_timestamp // window_size`

**TTL**: Keys expire after `2 × window_size` (covers current + previous window).

### Atomicity via Lua Scripts

A single Lua script executes the entire check-and-increment operation atomically in Redis:
1. Read previous window count
2. Calculate weight and estimated count
3. If over limit → return rejection with retry-after
4. INCR current window counter
5. If now over limit → DECR and reject
6. Set key TTL

Zero race conditions. O(1) time per request.

### Endpoint-Specific Limits

| Endpoint | Limit |
|---|---|
| `/api/v1/auth/login` | 20/minute |
| `/api/v1/auth/signup` | 10/minute |
| `/api/v1/sessions` | 100/minute |
| `/api/v1/admin/*` | 500/minute |
| `/api/v1/payments` | 30/minute |
| `/api/v1/cart` | 60/minute |

### Role-Based Limits

| Role | Limit |
|---|---|
| ADMIN | 1000/minute |
| THERAPIST | 200/minute |
| PATIENT | 100/minute |

### Response Headers

| Header | Description |
|---|---|
| `RateLimit-Limit` | Max requests per window |
| `RateLimit-Remaining` | Requests left in window |
| `RateLimit-Reset` | Unix timestamp when window resets |
| `Retry-After` | Seconds until retry (on 429) |

### Storage Backends

| Backend | Use Case |
|---|---|
| `RedisStorage` | Production — distributed, atomic, persistent |
| `MemoryStorage` | Development/testing — single-process, no persistence |

### Failure Strategy

**Fail-open**: If Redis is unreachable, requests are allowed through. Prevents rate limiting from becoming a single point of failure.

### Access Lists

- **Whitelist**: Identifiers bypass rate limiting entirely (e.g., internal services, monitoring)
- **Blacklist**: Identifiers are blocked with 403 (e.g., known attackers)
- Both support TTL-based expiration

### Metrics (Prometheus)

| Metric | Type | Description |
|---|---|---|
| `rate_limit_requests_allowed` | counter | Total allowed requests |
| `rate_limit_requests_blocked` | counter | Total blocked requests |
| `rate_limit_redis_errors` | counter | Redis connection/script errors |
| `rate_limit_storage_fallbacks` | counter | Fail-open activations |
| `rate_limit_redis_latency_ms` | gauge | Average Redis round-trip latency |
| `rate_limit_active_keys` | gauge | Number of active rate limit keys |
| `rate_limit_whitelist_hits` | counter | Whitelist bypass count |
| `rate_limit_blacklist_hits` | counter | Blacklist block count |

### Middleware vs Dependency

- **Middleware** (`RateLimitMiddleware`): Applied globally to all requests via `app.add_middleware()`. Resolves identifier from JWT or IP.
- **Dependency** (`rate_limit()`): Applied per-route via `Depends(rate_limit(limit=20, window=60))`. For endpoint-specific overrides.
