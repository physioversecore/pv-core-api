# Sahayatri Physio API

Backend API for the Sahayatri Physiotherapy platform. Built with **Python**, **FastAPI**, and **Prisma ORM** (PostgreSQL). Supports Patients, Therapists, and Admin roles with session booking, product shop, cart, payments, and reporting.

## Features

- JWT-based authentication (signup, login, role-based access)
- Therapist management (profiles, listings, approvals)
- Session booking (home visit / clinic, scheduling, status tracking)
- Product shop (equipment, medicine, nutrition — buy or rent)
- Shopping cart with rental day calculation and delivery fee logic
- Payment tracking
- Patient progress reports
- Admin dashboard (manage users, therapists, sessions, payments)
- Distributed rate limiting (Redis-backed Sliding Window Counter)
- Auto-generated Swagger docs & ReDoc

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
- Schema auto-pushed on startup

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
  main.py                # FastAPI app, CORS, lifespan, router includes, rate limit middleware
  config.py              # pydantic-settings (reads .env) — includes Redis & rate limit config
  database.py            # Prisma client singleton
  deps.py                # JWT auth dependencies
  models/                # Pydantic request/response schemas
  routers/               # API route handlers
  services/              # Business logic layer
  rate_limit/            # Distributed rate limiting system (Redis-backed)
    config.py            # Rate limiting rules & configuration
    storage.py           # Redis + Memory storage backends
    algorithms.py        # Sliding Window Counter + Token Bucket
    lua_scripts.py       # Atomic Redis Lua scripts
    middleware.py         # Global ASGI middleware
    dependencies.py      # Route-level FastAPI dependency
    access_list.py       # Whitelist/blacklist with TTL
    metrics.py           # Prometheus-compatible metrics
prisma/
  schema.prisma          # Prisma ORM schema (14 models)
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
| POST | `/api/v1/auth/signup` | Register new user | Public |
| POST | `/api/v1/auth/login` | Login, returns JWT | Public |
| GET | `/api/v1/auth/me` | Get current user profile | Authenticated |

### Therapists
| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/v1/therapists` | List therapists | Public |
| GET | `/api/v1/therapists/me` | My therapist profile | Therapist |
| POST | `/api/v1/therapists` | Create therapist profile | Therapist |
| GET | `/api/v1/therapists/{id}` | Get therapist by ID | Public |
| PUT | `/api/v1/therapists/{id}` | Update therapist profile | Owner/Admin |
| DELETE | `/api/v1/therapists/{id}` | Delete therapist | Owner/Admin |

### Sessions (Bookings)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/api/v1/sessions` | Book a session | Patient |
| GET | `/api/v1/sessions` | List my sessions | Patient/Therapist/Admin |
| GET | `/api/v1/sessions/{id}` | Get session details | Authenticated |
| PUT | `/api/v1/sessions/{id}` | Update session | Patient/Admin |
| DELETE | `/api/v1/sessions/{id}` | Cancel session | Patient/Admin |

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
| POST | `/api/v1/payments` | Create payment | Authenticated |
| GET | `/api/v1/payments` | List payments | User (own) / Admin (all) |
| GET | `/api/v1/payments/{id}` | Get payment details | Authenticated |
| PUT | `/api/v1/payments/{id}/status` | Update payment status | Admin |

### Reports
| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/api/v1/reports` | Create progress report | Therapist/Admin |
| GET | `/api/v1/reports` | List reports | Patient (own) / Therapist/Admin |
| GET | `/api/v1/reports/{id}` | Get report details | Authenticated |
| PUT | `/api/v1/reports/{id}` | Update report | Therapist/Admin |
| DELETE | `/api/v1/reports/{id}` | Delete report | Therapist/Admin |

### Admin
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/admin/users` | List all users (filter by role) |
| PUT | `/api/v1/admin/users/{id}/status` | Approve/reject therapist |
| GET | `/api/v1/admin/payments` | List all payments |
| GET | `/api/v1/admin/sessions` | List all sessions |
| GET | `/api/v1/admin/therapists/pending` | List pending therapists |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/sahayatri_physio` | PostgreSQL connection string |
| `SECRET_KEY` | — | JWT signing secret (change in production!) |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token expiry in minutes (24h) |
| `UVICORN_RELOAD` | `true` | Enable/disable hot reload |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string (rate limiting) |
| `RATE_LIMIT_ENABLED` | `true` | Enable/disable rate limiting |
| `RATE_LIMIT_DEFAULT_LIMIT` | `100` | Default requests per window |
| `RATE_LIMIT_DEFAULT_WINDOW` | `60` | Default window size in seconds |
| `RATE_LIMIT_STORAGE_BACKEND` | `redis` | Storage backend (`redis` or `memory`) |

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

14 models: `User`, `Therapist`, `Product`, `Session`, `Review`, `Report`, `Payment`, `CartItem`, `Setting`, `AvailabilitySlot`, `RecurringPattern`, `AvailabilityBlock`, `AuditLogEntry`, `ScheduleBlockRequest`.

After modifying `prisma/schema.prisma`:

```sh
uv run prisma generate     # regenerate Python client
uv run prisma db push       # sync schema to database (dev only)
```

For production migrations, use `prisma migrate dev` to create migration files, then `prisma migrate deploy` in production.
