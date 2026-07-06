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
| Auth | JWT (python-jose) + bcrypt |
| Package mgr | uv |

---

## Project Structure

```
main.py                  # CLI entrypoint (uvicorn with hot reload)
app/
  __init__.py            # Re-exports all public symbols from submodules
  main.py                # FastAPI app, CORS, lifespan, router includes
  config.py              # pydantic-settings (reads .env)
  database.py            # Prisma client singleton
  deps.py                # Reusable deps: JWT auth, pagination, get_or_404
  models/                # Pydantic request/response schemas per domain
  routers/               # Route handlers per domain
  services/              # Business logic layer
prisma/
  schema.prisma          # Prisma schema (8 models)
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
