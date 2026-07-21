# PVC API — Architecture

## Overview

PVC API is the backend for the Sahayatri Physiotherapy platform. Built with **Python 3.13**, **FastAPI**, and **Prisma ORM** (PostgreSQL). Supports three user roles:

- **Patients** — Book sessions, shop products, track reports
- **Therapists** — Manage schedules, submit reports, track earnings
- **Admins** — Approve therapists, manage users, oversee bookings/payments

---

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.13 |
| Framework | FastAPI |
| ORM | Prisma (Python) |
| Database | PostgreSQL 16 |
| Cache/Rate Limiting | Redis 7 |
| Auth | JWT (python-jose) + bcrypt |
| Package mgr | uv |

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
  models/                # Pydantic request/response schemas per domain
  routers/               # Route handlers per domain
  services/              # Business logic layer
  rate_limit/            # Distributed rate limiting system (Redis-backed)
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
  schema.prisma          # Prisma schema (14 models)
```

---

## Module Layer Rules

- **`app/__init__.py`** — Re-exports all public symbols from `models/`, `services/`, `routers/`, `deps.py`, `database.py`. Consumers always `from app import X`.
- **Routers** — Handle HTTP concerns (parsing, validation, status codes, response shapes). Delegate all DB/business logic to services.
- **Services** — Business logic and Prisma queries. No HTTP awareness.
- **Models** — Pure Pydantic schemas. No DB or HTTP logic.

---

## Reusable Dependencies (`app/deps.py`)

| Dependency | Purpose |
|---|---|
| `get_current_user` | Decode JWT, return `User` or 401 |
| `get_admin_user` | Wraps `get_current_user`, checks `role == ADMIN` |
| `pagination_params` | Returns `{"skip": int, "limit": int}` from query params (defaults 0, 100) |
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
| POST | `/auth/signup` | Public |
| POST | `/auth/login` | Public |
| GET  | `/auth/me` | Authenticated |
| PUT  | `/auth/me` | Authenticated |
| POST | `/auth/change-password` | Authenticated |

### Therapists
| Method | Path | Access |
|---|---|---|
| GET  | `/therapists` | Public |
| POST | `/therapists` | Therapist |
| GET  | `/therapists/me` | Therapist |
| GET  | `/therapists/{id}` | Public |
| PUT  | `/therapists/{id}` | Owner/Admin |
| DEL  | `/therapists/{id}` | Owner/Admin |

### Sessions
| Method | Path | Access |
|---|---|---|
| POST | `/sessions` | Patient |
| GET  | `/sessions` | Patient/Therapist/Admin |
| GET  | `/sessions/{id}` | Authenticated |
| PUT  | `/sessions/{id}` | Patient/Admin |
| DEL  | `/sessions/{id}` | Patient/Admin |

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
| POST | `/payments` | Authenticated |
| GET  | `/payments` | User (own) / Admin (all) |
| GET  | `/payments/{id}` | Authenticated |
| PUT  | `/payments/{id}/status` | Admin |

### Reports
| Method | Path | Access |
|---|---|---|
| POST | `/reports` | Therapist/Admin |
| GET  | `/reports` | Patient (own) / Therapist+Admin (by patient_id) |
| GET  | `/reports/{id}` | Authenticated |
| PUT  | `/reports/{id}` | Therapist/Admin |
| DEL  | `/reports/{id}` | Therapist/Admin |

### Admin
| Method | Path | Access |
|---|---|---|
| GET  | `/admin/users` | Admin |
| PUT  | `/admin/users/{id}/status` | Admin |
| GET  | `/admin/therapists/pending` | Admin |

---

## Database Schema (8 models)

- **User** — `id, name, email, password, role, city, phone, specialty, status`
- **Therapist** — `id, userId, name, specialty, city, gender, rating, reviews, price, experience, bio`
- **Product** — `id, name, category, price, rentPerDay, inStock, emoji, description, imageUrl`
- **Session** — `id, therapistId, patientId, date, time, type, status, address, fee, notes`
- **Report** — `id, patientId, sessionId, title, content, fileUrl`
- **Payment** — `id, userId, amount, status, method, sessionId`
- **CartItem** — `id, userId, productId, type, quantity, rentalDays`

---

## Key Design Decisions

1. **Three-layer architecture** — routers → services → Prisma. Services encapsulate business logic; routers handle HTTP.
2. **Role-based access** — JWT payload carries `sub` (user id); endpoints use `get_current_user` / `get_admin_user` dependencies.
3. **DRY dependencies** — `pagination_params` and `get_or_404` eliminate repeated pagination + existence-check boilerplate.
4. **`__init__.py` re-exports** — All public symbols are re-exported from `app/__init__.py`. Consumers always `from app import X`.
5. **Flat route structure** — `/{resource}` and `/{resource}/{id}` pattern; no nested sub-resources.
6. **Cart totals** — Computed in-memory: rental items use `price × qty × rentalDays`; delivery free above Rs 2,000.
7. **Distributed rate limiting** — Redis-backed Sliding Window Counter with atomic Lua scripts. Fail-open on Redis failure.

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

### 429 Response

```json
{
    "success": false,
    "error": "Rate limit exceeded.",
    "retry_after": 42
}
```

### Storage Backends

| Backend | Use Case |
|---|---|
| `RedisStorage` | Production — distributed, atomic, persistent |
| `MemoryStorage` | Development/testing — single-process, no persistence |

### Failure Strategy

**Fail-open**: If Redis is unreachable, requests are allowed through. Prevents rate limiting from becoming a single point of failure. The `storage_fallbacks` metric tracks when this happens.

### Configuration (`.env`)

```
REDIS_URL=redis://localhost:6379/0
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT_LIMIT=100
RATE_LIMIT_DEFAULT_WINDOW=60
RATE_LIMIT_STORAGE_BACKEND=redis
```

### Middleware vs Dependency

- **Middleware** (`RateLimitMiddleware`): Applied globally to all requests via `app.add_middleware()`. Resolves identifier from JWT or IP.
- **Dependency** (`rate_limit()`): Applied per-route via `Depends(rate_limit(limit=20, window=60))`. For endpoint-specific overrides.

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

### Access Lists

- **Whitelist**: Identifiers bypass rate limiting entirely (e.g., internal services, monitoring)
- **Blacklist**: Identifiers are blocked with 403 (e.g., known attackers)
- Both support TTL-based expiration

### Integration

Initialized during FastAPI lifespan. On Redis failure, automatically degrades to `MemoryStorage`:

```python
# app/main.py lifespan
if settings.rate_limit_enabled:
    config = build_config(redis_url=settings.redis_url, ...)
    _limiter = create_limiter(config)
    await _limiter.storage.connect()
```

Route-level usage (optional):
```python
from app.rate_limit import rate_limit

@router.post("/auth/login")
async def login(...= Depends(rate_limit(limit=20, window=60))):
    ...
```
