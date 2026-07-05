# Seed Data Guide — Sahayatri Physio Backend

This document maps all frontend mock data to backend seed scripts. Refer to this when seeding the PostgreSQL database for development or testing.

> **Backend schema**: `pvc-api/prisma/schema.prisma`  
> **Existing seed script**: `pvc-api/scripts/seed-users.py`  
> **Backend endpoints**: All under `http://localhost:8000/api/v1/`

---

## 1. Users (`User` model)

| Field | Type | Notes |
|---|---|---|
| `id` | cuid | Auto-generated |
| `name` | String | |
| `email` | String (unique) | |
| `password` | String | bcrypt-hashed |
| `role` | Enum: `PATIENT`, `THERAPIST`, `ADMIN` | |
| `city` | String? | |
| `phone` | String? | |
| `specialty` | String? | Only for therapists |
| `status` | Enum: `PENDING`, `APPROVED`, `REJECTED` | |

### Seed Users

| Name | Email | Password | Role | City | Phone | Status |
|---|---|---|---|---|---|---|
| John Doe | `patient@test.com` | `password123` | PATIENT | Kathmandu | 9800000001 | APPROVED |
| Dr. Jane Smith | `therapist@test.com` | `password123` | THERAPIST | Kathmandu | 9800000002 | APPROVED |
| Admin User | `admin@test.com` | `password123` | ADMIN | Kathmandu | 9800000003 | APPROVED |
| Ramesh Adhikari | `ramesh@test.com` | `password123` | PATIENT | Kathmandu | 9800000004 | APPROVED |
| Sita Lama | `sita@test.com` | `password123` | PATIENT | Lalitpur | 9800000005 | APPROVED |
| Hari Pradhan | `hari@test.com` | `password123` | PATIENT | Bhaktapur | 9800000006 | APPROVED |
| Dr. Aarati Shrestha | `aarati@test.com` | `password123` | THERAPIST | Kathmandu | 9800000007 | APPROVED |
| Dr. Bibek Thapa | `bibek@test.com` | `password123` | THERAPIST | Lalitpur | 9800000008 | APPROVED |
| Dr. Sushmita Rai | `sushmita@test.com` | `password123` | THERAPIST | Kathmandu | 9800000009 | APPROVED |
| Dr. Nirajan Karki | `nirajan@test.com` | `password123` | THERAPIST | Pokhara | 9800000010 | APPROVED |
| Dr. Sabina Gurung | `sabina@test.com` | `password123` | THERAPIST | Bhaktapur | 9800000011 | APPROVED |
| Dr. Rajan Magar | `rajan@test.com` | `password123` | THERAPIST | Chitwan | 9800000012 | APPROVED |
| Dr. Priya Tamang | `priya@test.com` | `password123` | THERAPIST | Biratnagar | 9800000013 | APPROVED |
| Dr. Anil Shakya | `anil@test.com` | `password123` | THERAPIST | Lalitpur | 9800000014 | APPROVED |

---

## 2. Therapists (`Therapist` model)

Linked to Users via `userId` (1:1). The "name" duplicates User.name for display convenience.

| Field | Type | Notes |
|---|---|---|
| `id` | cuid | Auto-generated |
| `userId` | String (unique) | FK → User.id |
| `name` | String | |
| `specialty` | String | |
| `city` | String | |
| `gender` | String | "Male" or "Female" |
| `rating` | Float | Default 0.0 |
| `reviews` | Int | Default 0 |
| `price` | Float | Per session (NPR) |
| `experience` | Int | Years |
| `bio` | String | |

### Seed Therapists

> Create the User first (section 1), then create the Therapist profile with the corresponding `userId`.

| Name | Specialty | City | Gender | Rating | Reviews | Price | Experience | Bio |
|---|---|---|---|---|---|---|---|---|
| Dr. Aarati Shrestha | Sports & post-surgery | Kathmandu | Female | 4.9 | 128 | 1500 | 8 | Specialist in ACL and rotator cuff rehab with 8+ years of home-visit experience. |
| Dr. Bibek Thapa | Musculoskeletal | Lalitpur | Male | 4.8 | 96 | 1200 | 6 | Manual therapy and dry needling specialist. |
| Dr. Sushmita Rai | Geriatric & neuro | Kathmandu | Female | 4.9 | 142 | 1400 | 10 | Stroke and Parkinson's rehab for elderly patients. |
| Dr. Nirajan Karki | Pediatric rehab | Pokhara | Male | 4.7 | 67 | 1300 | 5 | Cerebral palsy and developmental delays. |
| Dr. Sabina Gurung | Neurological | Bhaktapur | Female | 4.8 | 84 | 1600 | 9 | Post-stroke and spinal cord rehabilitation. |
| Dr. Rajan Magar | Post-operative | Chitwan | Male | 4.6 | 51 | 1100 | 4 | Post-op knee and hip recovery. |
| Dr. Priya Tamang | General | Biratnagar | Female | 4.7 | 73 | 1000 | 5 | General home physiotherapy and pain management. |
| Dr. Anil Shakya | Sports & post-surgery | Lalitpur | Male | 4.9 | 110 | 1700 | 11 | Former national team physio. |

---

## 3. Products (`Product` model)

| Field | Type | Notes |
|---|---|---|
| `id` | cuid | Auto-generated |
| `name` | String | |
| `category` | Enum: `EQUIPMENT`, `MEDICINE`, `NUTRITION` | |
| `price` | Float | NPR |
| `rentPerDay` | Float | Default 0 (only for rentable equipment) |
| `inStock` | Int | 1 = in stock, 0 = out of stock |
| `emoji` | String | Display emoji |
| `description` | String? | |
| `imageUrl` | String? | Optional image |

### Seed Products

#### Equipment (EQUIPMENT)

| Name | Price | RentPerDay | InStock | Emoji | Description |
|---|---|---|---|---|---|
| Standard Wheelchair | 18000 | 150 | 1 | ♿ | Foldable, lightweight, 100kg capacity. |
| Adjustable Crutches (Pair) | 2200 | 40 | 1 | 🩼 | Aluminum, height adjustable. |
| TENS Therapy Unit | 4500 | 80 | 1 | ⚡ | Dual-channel pain relief device. |
| Hot & Cold Therapy Pack | 850 | 20 | 1 | 🧊 | Reusable gel pack with strap. |
| Knee Support Brace | 1600 | 0 | 1 | 🦵 | Post-op stabilizing brace. |
| Walker with Wheels | 6500 | 60 | 0 | 🚶 | Senior-friendly mobility walker. |

#### Medicine (MEDICINE)

| Name | Price | InStock | Emoji | Description |
|---|---|---|---|---|
| Ibuprofen 400mg (10 tabs) | 120 | 1 | 💊 | Pain & inflammation relief. |
| Diclofenac Gel 30g | 240 | 1 | 🧴 | Topical anti-inflammatory. |
| Calcium + D3 (30 tabs) | 380 | 1 | 🦴 | Bone health supplement. |
| Muscle Relaxant (10 tabs) | 280 | 1 | 💊 | Rx — uploaded by therapist. |

#### Nutrition (NUTRITION)

| Name | Price | InStock | Emoji | Description |
|---|---|---|---|---|
| Whey Protein 1kg | 3200 | 1 | 🥤 | Muscle recovery support. |
| Collagen Peptides 250g | 2400 | 1 | 🍶 | Joint & tissue repair. |
| Omega-3 (60 caps) | 1100 | 1 | 🐟 | Anti-inflammatory. |
| Recovery Meal Plan (1 week) | 1800 | 1 | 🍱 | Nepali-style nutrition plan. |

---

## 4. Sessions (`Session` model)

| Field | Type | Notes |
|---|---|---|
| `id` | cuid | Auto-generated |
| `therapistId` | String | FK → Therapist.id |
| `patientId` | String | FK → User.id |
| `date` | DateTime | Session date |
| `time` | String | e.g. "10:00" |
| `type` | Enum: `HOME_VISIT`, `CLINIC` | |
| `status` | Enum: `SCHEDULED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED` | |
| `address` | String | Patient's home address |
| `fee` | Float | Session fee (NPR) |
| `notes` | String? | Optional session notes |

### Seed Sessions

Mapped mock data — requires Users and Therapists to be seeded first.

| Therapist | Patient | Date | Time | Type | Status | Address | Fee |
|---|---|---|---|---|---|---|---|
| Dr. Aarati Shrestha | Ramesh Adhikari | 2026-07-02 | 10:00 | HOME_VISIT | SCHEDULED | Baluwatar, Kathmandu | 1500 |
| Dr. Bibek Thapa | Sita Lama | 2026-07-05 | 16:00 | HOME_VISIT | SCHEDULED | Jhamsikhel, Lalitpur | 1200 |
| Dr. Aarati Shrestha | Ramesh Adhikari | 2026-06-20 | 11:00 | HOME_VISIT | COMPLETED | Baluwatar, Kathmandu | 1500 |
| Dr. Sushmita Rai | Hari Pradhan | 2026-06-18 | 09:00 | HOME_VISIT | COMPLETED | Bhaktapur | 1400 |
| Dr. Bibek Thapa | Sita Lama | 2026-06-12 | 14:00 | HOME_VISIT | CANCELLED | Jhamsikhel, Lalitpur | 1200 |

---

## 5. Cart Items (`CartItem` model)

| Field | Type | Notes |
|---|---|---|
| `id` | cuid | Auto-generated |
| `userId` | String | FK → User.id |
| `productId` | String | FK → Product.id |
| `type` | Enum: `BUY`, `RENT`, `MEDICINE`, `NUTRITION` | |
| `quantity` | Int | Default 1 |
| `rentalDays` | Int | Default 7 (only for RENT type) |

Cart is user-specific and dynamic — no seed data required. Users add items via the shop interface. The backend computes totals server-side.

---

## 6. Payments (`Payment` model)

| Field | Type | Notes |
|---|---|---|
| `id` | cuid | Auto-generated |
| `userId` | String | FK → User.id |
| `amount` | Float | |
| `status` | String | Default "PENDING" |
| `method` | String | Default "CASH" |
| `sessionId` | String? | Optional FK → Session.id |

Payments are created during booking flow — no seed data required.

---

## 7. Reports (`Report` model)

| Field | Type | Notes |
|---|---|---|
| `id` | cuid | Auto-generated |
| `patientId` | String | FK → User.id |
| `sessionId` | String? | Optional FK → Session.id |
| `title` | String | |
| `content` | String | Report body |
| `fileUrl` | String? | Optional file attachment |

### Seed Reports

| Patient | Session | Title | Content |
|---|---|---|---|
| Ramesh Adhikari | 2026-06-20 session | Progress report — week 4 | Range of motion improving. Patient can now flex knee to 110°. Continue with quad sets and hamstring stretches. |
| Hari Pradhan | 2026-06-18 session | Session note — Stroke rehab | Upper limb coordination exercises introduced. Patient responds well to mirror therapy. |

---

## 8. Static Data (used by UI)

### Cities (from CITIES constant)

```
Kathmandu, Lalitpur, Bhaktapur, Pokhara, Chitwan, Biratnagar
```

### Specialties (from SPECIALTIES constant)

```
Sports & post-surgery, Musculoskeletal, Geriatric & neuro, Pediatric rehab, Neurological, Post-operative, General
```

These are human-readable strings stored in `Therapist.specialty` and used as filter options in the UI. They are not a separate database enum — they are free-text fields in the `Therapist` model.

---

## How to Run the Seed Script

```bash
cd pvc-api

# Ensure virtual environment is active and dependencies installed
uv sync

# Start PostgreSQL via Docker (if not already running)
docker compose up -d db

# Run seed script
uv run python scripts/seed-users.py
```

This seeds 14 users + 8 therapist profiles. For products, sessions, and reports, extend `scripts/seed-users.py` or create a new `scripts/seed-all.py` using the same pattern.

---

## API Endpoint Reference for Frontend Developers

| Purpose | Method | Endpoint | Auth |
|---|---|---|---|
| List therapists | GET | `/api/v1/therapists?skip=0&limit=100` | Public |
| Get therapist | GET | `/api/v1/therapists/{id}` | Public |
| List products | GET | `/api/v1/products?category=EQUIPMENT` | Public |
| Login | POST | `/api/v1/auth/login` | Public |
| Signup | POST | `/api/v1/auth/signup` | Public |
| Get current user | GET | `/api/v1/auth/me` | JWT |
| List sessions | GET | `/api/v1/sessions?skip=0&limit=100` | JWT |
| Create session | POST | `/api/v1/sessions` | JWT (PATIENT) |
| Get cart | GET | `/api/v1/cart` | JWT |
| Add to cart | POST | `/api/v1/cart` | JWT |
| Admin: list users | GET | `/api/v1/admin/users?role=THERAPIST` | JWT (ADMIN) |
| Admin: update status | PUT | `/api/v1/admin/users/{id}/status?new_status=APPROVED` | JWT (ADMIN) |
| Admin: pending therapists| GET | `/api/v1/admin/therapists/pending` | JWT (ADMIN) |

> **Base URL**: `http://localhost:8000` (dev) — configured via `BACKEND_URL` env var on the frontend.
