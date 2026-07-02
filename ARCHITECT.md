# Sahayatri Physio — Architecture

## Overview
Sahayatri Physio is a multi-role physiotherapy platform serving three user types:

- **Patients** — Book home-visit physiotherapy sessions, buy/rent equipment and medicines, track recovery progress.
- **Therapists** — Manage schedules, upload session reports, track earnings, refer colleagues.
- **Admins** — Approve therapists, manage patients, oversee bookings and payments.

The app is a fully client-rendered SPA (all dashboard pages are `"use client"`) with localStorage-based auth and cart. There is no real backend — all data is mocked in `src/lib/mock.ts`.

---

## Routes (Next.js App Router)

### Public
| Route | File | Description |
|---|---|---|
| `/` | `src/app/page.tsx` | Landing page with therapist discovery, features, signup CTA |

### Admin Dashboard (`/admin/*`)
| Route | File |
|---|---|
| `/admin` | `app/(dashboard)/admin/page.tsx` |
| `/admin/bookings` | `app/(dashboard)/admin/bookings/page.tsx` |
| `/admin/patients` | `app/(dashboard)/admin/patients/page.tsx` |
| `/admin/payments` | `app/(dashboard)/admin/payments/page.tsx` |
| `/admin/settings` | `app/(dashboard)/admin/settings/page.tsx` |
| `/admin/therapists` | `app/(dashboard)/admin/therapists/page.tsx` |

### Patient Dashboard (`/patient/*`)
| Route | File |
|---|---|
| `/patient` | `app/(dashboard)/patient/page.tsx` |
| `/patient/sessions` | `app/(dashboard)/patient/sessions/page.tsx` |
| `/patient/shop` | `app/(dashboard)/patient/shop/page.tsx` |
| `/patient/progress` | `app/(dashboard)/patient/progress/page.tsx` |
| `/patient/reports` | `app/(dashboard)/patient/reports/page.tsx` |
| `/patient/profile` | `app/(dashboard)/patient/profile/page.tsx` |
| `/patient/help` | `app/(dashboard)/patient/help/page.tsx` |
| `/patient/settings` | `app/(dashboard)/patient/settings/page.tsx` |

### Therapist Dashboard (`/therapist/*`)
| Route | File |
|---|---|
| `/therapist` | `app/(dashboard)/therapist/page.tsx` |
| `/therapist/schedule` | `app/(dashboard)/therapist/schedule/page.tsx` |
| `/therapist/reports` | `app/(dashboard)/therapist/reports/page.tsx` |
| `/therapist/patients` | `app/(dashboard)/therapist/patients/page.tsx` |
| `/therapist/earnings` | `app/(dashboard)/therapist/earnings/page.tsx` |
| `/therapist/profile` | `app/(dashboard)/therapist/profile/page.tsx` |
| `/therapist/settings` | `app/(dashboard)/therapist/settings/page.tsx` |

---

## Layout Hierarchy

```
<html>                              # src/app/layout.tsx — fonts, <Providers>
  <body>
    <Providers>                     # src/app/providers.tsx
      <QueryClientProvider>
        <AuthProvider>
          <CartProvider>
            <LangProvider>
              <Toaster />
              {children}            # → landing page (/) or dashboard layout
            </LangProvider>
          </CartProvider>
        </AuthProvider>
      </QueryClientProvider>
    </Providers>
  </body>
</html>

When pathname starts with /admin, /patient, or /therapist:

  DashboardLayout (client)          # src/app/(dashboard)/layout.tsx
    ↓ derives nav, title, showCart from usePathname()
    <DashboardShell nav={nav} title={title} showCart={showCart}>
      <page.tsx children />         # The specific dashboard page
    </DashboardShell>
```

The `(dashboard)` route group wraps all authenticated pages. Its `layout.tsx` reads `usePathname()` to determine the role (`admin`/`patient`/`therapist`), looks up the matching `NavItem[]` from `src/lib/nav.tsx`, finds the current page label for the title, and passes everything to `DashboardShell`.

---

## State Management

### Auth (`src/lib/auth.tsx`)
- **Context**: `AuthProvider` → `useAuth()`
- **Storage**: `localStorage` under key `sahayatri.user`
- **User shape**: `{ id, name, email, role, city?, phone?, specialty?, status? }`
- **Roles**: `"patient" | "therapist" | "admin"`
- **Login**: Simulated — generates a `User` from email, stores to localStorage.
- **Signup**: Creates user with appropriate role; therapists start as `"pending"`.

### Cart (`src/lib/cart.tsx`)
- **Context**: `CartProvider` → `useCart()`
- **Storage**: `localStorage` under key `sahayatri.cart`
- **Items**: Can be `"buy"`, `"rent"`, `"medicine"`, or `"nutrition"` type.
- **Rental**: Rent items have `rentalDays` (default 7); line total = `price × qty × rentalDays`.
- **Delivery**: Free above Rs 2,000, otherwise Rs 150.
- **Persistence**: Cart auto-syncs to localStorage on every change via `useEffect`.

### Language (`src/lib/i18n.tsx`)
- Context-based Nepali/English toggle.

### Server State
- `@tanstack/react-query` (`QueryClientProvider`) is wired up but no real API calls exist yet — all data is from `mock.ts`.

---

## Data Layer

### Mock Data (`src/lib/mock.ts`)

| Data | Type | Fields |
|---|---|---|
| `THERAPISTS` | `Therapist[]` | id, name, specialty, city, gender, rating, reviews, price, experience, bio |
| `PRODUCTS` | `Product[]` | id, name, category (equipment/medicine/nutrition), price, rentPerDay, inStock, emoji |
| `MOCK_SESSIONS` | `Session[]` | id, therapist, date, time, type, status, patient, address, fee |

### Nav (`src/lib/nav.tsx`)
Defines three `NavItem[]` arrays — `patientNav`, `therapistNav`, `adminNav` — each with `to`, `label`, and `icon` (lucide-react element). Used by DashboardShell for the sidebar.

---

## UI Component Architecture

### DashboardShell (`src/components/DashboardShell.tsx`)
The main layout wrapper for all dashboard pages. Renders:
- **Sidebar**: Navigation links from `nav` prop, user avatar/name at bottom, role badge.
- **Header**: Page title, notification bell, cart icon (patient only), auth modal trigger.
- **Content area**: `{children}` from the page.

### Custom Components
| Component | Purpose |
|---|---|
| `AuthModal.tsx` | Login/signup modal with role selection, form validation |
| `Avatar.tsx` | Circular avatar showing initials from name string |
| `BookingModal.tsx` | Modal for booking sessions with therapist selection, date/time, address |
| `CartDrawer.tsx` | Slide-over drawer showing cart items, quantities, rental days, totals |
| `TherapistCard.tsx` | Card for therapist listings (photo placeholder, specialty, rating, price) |
| `NotificationBell.tsx` | Bell icon with unread count badge |
| `Reveal.tsx` | Scroll-triggered reveal animation wrapper |

### shadcn/ui Primitives (`src/components/ui/`)
51 components generated via shadcn CLI. Customized with the project's theme tokens. Used across pages for inputs, dialogs, selects, tables, etc.

---

## Styling System

### Theme (CSS Custom Properties)
Defined in `src/app/globals.css` using Tailwind v4's `@theme inline`:

```
--font-display: "Fraunces" (serif, headings)
--font-sans:    "Inter" (body)
--font-mono:    "IBM Plex Mono" (code/dates)

--pine:    #2F5D50  (primary green)
--sage:    #EEF1ED  (muted background)
--amber:   #E2962F  (accent)
--forest:  #1E2A2E  (foreground/dark)
--cream:   #FBFBF8  (background/light)
--slate:   #4A5854  (muted foreground)
```

### Custom Utility Classes (defined with `@utility`)
- `btn-primary` — Pine background, white text, rounded-full
- `btn-pine` — Same as btn-primary
- `btn-outline` — Ghost button with border
- `card-soft` — White card with border, rounded-2xl, shadow
- `chip` — Small label/badge
- `eyebrow` — Tiny uppercase label (`font-mono text-xs text-slate`)

### Dark Mode
Supported via `.dark` class on `<html>`. Flips `--background` to `--forest` and `--foreground` to `--cream`.

---

## Key Design Decisions

1. **Route group `(dashboard)`** — All authenticated pages share a single layout that derives nav from pathname, avoiding repetitive `DashboardShell` wrapping in each page.
2. **Client components only** — Every dashboard page is `"use client"` because they all use state, effects, or interactive event handlers. Server components are only used for the root layout and landing page.
3. **No real API** — The entire app runs on localStorage and mock data. `@tanstack/react-query` is configured for future backend integration.
4. **Flat route structure** — Each role's pages are flat under their prefix (e.g., `/patient/sessions`, not `/patient/sessions/list`).
5. **No data fetching library** for the mock phase — components access context and mock data directly.
6. **LocalStorage as database** — Auth and cart persist across sessions. Data is seeded on first login.
