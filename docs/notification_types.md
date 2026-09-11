# Notification types

The contract between the API's per-user notification feed and the clients that
render it. The client switches on `type`, so **the set of keys is an API
surface**: adding one is additive, renaming or removing one breaks every
installed app.

Source of truth: `NotificationType` and `RefType` in
`app/services/notification_events.py`. This document and that enum must not
drift; a test in `test/test_notification_events.py` asserts every producer uses
a registered key.

## Shape

`GET /api/v1/notifications` returns rows of:

| Field | Meaning |
|---|---|
| `id` | Row id, used by `POST /notifications/{id}/read`. |
| `type` | Machine key from the table below. **Treat an unknown key as a generic entry — never crash, never hide it.** |
| `title` | One line, already localised to English. Safe to render verbatim. |
| `body` | One or two sentences. Names the person, the money and the time. |
| `readAt` | `null` until read. A timestamp, not a flag, so *when* stays recoverable. |
| `refType` | What `refId` names. Empty when the event points nowhere. |
| `refId` | The id of that thing, for deep-linking. |
| `createdAt` | When the event happened. |

Rows are ordered newest first. `unread` on the list response is the count of
rows with `readAt == null` for that user.

## Rules a client can rely on

1. **One recipient per row.** A notification belongs to exactly one user. A
   shared event (a cancellation) is written as two rows with different copy.
2. **`type` is stable and uppercase snake case.** It always equals the enum
   member name.
3. **`refType` values are a closed set** (below), but a client that does not
   handle one must fall through gracefully rather than navigate somewhere that
   does not exist.
4. **Copy is written to be shown as-is.** Do not re-derive text from `type`.
5. **Duplicates are prevented server-side** for decisions (see *Idempotency*),
   but a client should still key its list on `id`.

## `refType` values

| `refType` | `refId` is | Suggested destination |
|---|---|---|
| `SESSION` | `Session.id` | The bookings/sessions screen (detail if there is one). |
| `PAYMENT` | `Payment.id` | Payment history. |
| `REFUND` | `Refund.id` | Refund/case detail; payment history is an acceptable fallback. |
| `REPORT` | `Report.id` | The patient's reports screen. |
| `THERAPIST` | `Therapist.id` | The therapist's own application/profile screen. |
| `RATE_CHANGE` | `RateChangeRequest.id` | The therapist's rate settings. |
| `LEAVE` | `ScheduleBlockRequest.id` | The therapist's availability/leave screen. |
| `REFERRAL` | See per-type notes | Refer & earn screen. |
| `POINTS` | *(none — `refId` is null)* | Rewards/points screen. |

## The registry

### Bookings

| `type` | Recipient | Raised when | `refType` / `refId` |
|---|---|---|---|
| `SESSION_BOOKED` | **Patient** | `POST /sessions` or `POST /payments/process` creates a session. | `SESSION` / session id |
| `SESSION_NEW_BOOKING` | **Therapist** | Same event, the other side of it. | `SESSION` / session id |
| `SESSION_RESCHEDULED` | **Both** (separate rows, different copy) | `PATCH /sessions/{id}/reschedule` — the patient moved the slot. | `SESSION` / session id |
| `SESSION_RESCHEDULE_REQUESTED` | **The party who did not ask** | `PUT /sessions/{id}` sets status `RESCHEDULE_REQUESTED`. | `SESSION` / session id |
| `SESSION_DECLINE_REQUESTED` | **Therapist only** | `PUT /sessions/{id}` sets status `DECLINE_REQUESTED`. | `SESSION` / session id |
| `SESSION_CANCELLED` | **Both** (separate rows, different copy) | `PUT /sessions/{id}` sets status `CANCELLED`, or `DELETE /sessions/{id}`. | `SESSION` / session id |
| `SESSION_COMPLETED` | **Therapist always; patient only when they cannot rate** | `PUT /sessions/{id}` sets status `COMPLETED`. | `SESSION` / session id |
| `SESSION_RATE_REQUEST` | **Patient** | Same event, when no review of that therapist exists yet. | `SESSION` / session id |

Notes:

* `SESSION_DECLINE_REQUESTED` is an acknowledgement to the therapist, not a
  warning to the patient. The patient hears nothing until the decision lands as
  a `SESSION_CANCELLED`.
* On completion the patient gets **either** `SESSION_RATE_REQUEST` **or**
  `SESSION_COMPLETED`, never both. `POST /reviews` rejects a second review of
  the same therapist, so the prompt is only sent while it would still work.
* `SCHEDULED` and `IN_PROGRESS` transitions are deliberately silent.

### Money

| `type` | Recipient | Raised when | `refType` / `refId` |
|---|---|---|---|
| `PAYMENT_RECEIVED` | **Payer** | A payment reaches status `COMPLETED`: `POST /payments/process` (which always settles), or an admin settling one with `PUT /payments/{id}/status`. `POST /payments` is also wired but records payments as `PENDING` today, so it does not fire. | `PAYMENT` / payment id |
| `REFUND_REQUESTED` | **Patient** | `POST /admin/refunds` opens a case on their booking. | `REFUND` / refund id |
| `REFUND_APPROVED` | **Patient** | `PUT /admin/refunds/{id}` sets status `Approved`. | `REFUND` / refund id |
| `REFUND_DENIED` | **Patient** | `PUT /admin/refunds/{id}` sets status `Denied`. Carries the admin's reason when one was recorded. | `REFUND` / refund id |

### Therapist lifecycle

| `type` | Recipient | Raised when | `refType` / `refId` |
|---|---|---|---|
| `APPLICATION_APPROVED` | **Therapist** | `PUT /admin/therapists/{id}/approve`, or `PUT /admin/verifications/{id}` with status `Verified`. | `THERAPIST` / therapist id |
| `APPLICATION_REJECTED` | **Therapist** | The rejection equivalents of the above. Carries the admin's note. | `THERAPIST` / therapist id |
| `RATE_CHANGE_APPROVED` | **Therapist** | `PUT /rate-change/{id}/approve`. Names the new rate. | `RATE_CHANGE` / request id |
| `RATE_CHANGE_REJECTED` | **Therapist** | `PUT /rate-change/{id}/reject`. Carries admin notes. | `RATE_CHANGE` / request id |
| `LEAVE_APPROVED` | **Therapist** | `PUT /availability/block-requests/{id}/approve`. Names the date span. | `LEAVE` / request id |
| `LEAVE_REJECTED` | **Therapist** | `PUT /availability/block-requests/{id}/reject`. | `LEAVE` / request id |

> **Visibility caveat.** A therapist whose account is not `APPROVED` cannot
> authenticate (`get_current_user` rejects them), so `APPLICATION_REJECTED` is
> written but effectively unreadable until the account is later approved. The
> rejection email is what actually reaches them. The row is kept as the record.

### Care record

| `type` | Recipient | Raised when | `refType` / `refId` |
|---|---|---|---|
| `REPORT_UPLOADED` | **Patient** | `POST /reports` (multipart) files a report or exercise plan for them. Names the therapist and the report title. | `REPORT` / report id |

### Rewards

| `type` | Recipient | Raised when | `refType` / `refId` |
|---|---|---|---|
| `REFERRAL_JOINED` | **Referrer** | `POST /auth/signup` with a valid referral code attributes a new user to them. | `REFERRAL` / the **new user's** id |
| `REFERRAL_REWARDED` | **Referrer** (and referee, if `referralAwardsBothSides` is on) | A referred patient's first session is completed and the ledger pays out. | `REFERRAL` / the **PointTransaction** id |
| `POINTS_MATURED` | **Owner of the points** | Held points clear their hold and become spendable. Maturation happens lazily on a balance read. | `POINTS` / *none* |

## Idempotency

Two mechanisms, both server-side:

1. **`notify_once`** refuses to write a second row with the same
   `(userId, type, refId)`. Every decision-shaped event uses it, because the
   endpoints behind them are re-callable: `PUT /admin/therapists/{id}/approve`
   happily re-approves an approved therapist, and
   `PUT /availability/block-requests/{id}/approve` does not check the current
   status at all.
2. **Transition guards** in the routers. `PUT /sessions/{id}` also edits notes
   and times, so notifications only fire when `status` actually changed;
   `PUT /admin/refunds/{id}` only announces a decision when the refund was not
   already decided; `PUT /payments/{id}/status` only receipts a payment that
   was not already `COMPLETED`.

Events that can legitimately recur for the same subject —
`SESSION_RESCHEDULED`, `SESSION_RESCHEDULE_REQUESTED`, `POINTS_MATURED` — do
**not** dedupe on `refId`, since a second occurrence is genuinely new. For
`POINTS_MATURED` no guard is needed: `PENDING` becomes `AVAILABLE` exactly
once, so the same points cannot be announced twice.

## Failure behaviour

A notification never fails the request that caused it. Writes go through
`safe_notify`, which swallows and logs, and callers schedule them through
FastAPI `BackgroundTasks`. The one exception is `DELETE /sessions/{id}`, where
the producer runs inline *before* the row is deleted — a background task would
find nothing left to describe. It is still swallowed, so the delete cannot
fail because of it.

## Not produced (and why)

These appear in the mobile designs or in the client's icon switch but have no
trigger point in the API today. Nothing fabricates them.

| Design item / key | Why not | What it would take |
|---|---|---|
| **New message** ("Anisha shared post-session exercises") | There is no messaging feature: no model, no endpoints, nothing that sends a message between a patient and a therapist. | A `Message` model and endpoints. The closest thing that exists is `REPORT_UPLOADED`, which is what a therapist sharing exercises actually produces today. |
| **Session reminder** / `SESSION_REMINDER` ("Your home visit starts in 1 hour") | Time-triggered, and the API has no scheduler. Every existing background task is request-scoped (`BackgroundTasks`), which cannot fire an hour before an event nobody is requesting. | A periodic worker (cron container, Celery/APScheduler, or a Render cron job) that sweeps `Session` rows with `status = SCHEDULED` inside the next window, writes the notification, and records that it did so — a `reminderSentAt` column on `Session`, or the `notify_once` key `(userId, SESSION_REMINDER, sessionId)` — so a re-run does not re-notify. Add `SESSION_REMINDER` to the registry at that point, not before. |
| `POINTS_EXPIRING` | Also time-triggered, and expiry is switched off at launch (`expiryDays: None` in the points config). | The same scheduler, plus expiry being turned on. |
| Sessions cancelled by an approved leave request | `block_range` **counts** booked slots it collides with (`cancelledCount`, `affectedPatients`) but does not change any session's status. No cancellation actually happens, so there is nothing truthful to announce to those patients. | Make leave approval genuinely cancel the colliding sessions; the existing `SESSION_CANCELLED` producer then covers it with no new key. |
