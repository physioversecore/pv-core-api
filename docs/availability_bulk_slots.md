# Bulk availability — "which therapists are free at T?"

The contract for `GET /api/v1/availability/slots/bulk`, and the two rules about
the slot grid that every availability caller needs to know.

Source of truth: `get_bulk_slots_for_range` and `get_slots_for_range` in
`app/services/availability.py`; response models in `app/models/availability.py`;
route in `app/routers/availability.py`. Tests: `test/test_availability.py`.

---

## 1. How a slot gets its status

Both the single-therapist reads and the bulk read answer from the same
synthesis, so a therapist reads the same on their profile as in a bulk answer.

The grid is **synthesised, not stored**. For each day in the window, the
therapist's working hours (`Setting` key `wh_<userId>`, defaulting to
09:00–18:00 in `sessionDuration + breakDuration` steps, Mon–Fri) produce a list
of `HH:MM` start times. Stored state is then laid over that list, in this order
of precedence:

| Precedence | Source | Status |
|---|---|---|
| 1 | A `Session` at that date+time | `booked` |
| 2 | An `AvailabilitySlot` row already saying `booked` | `booked` |
| 3 | An `AvailabilityBlock` covering that date+time | `off` |
| 4 | An `AvailabilitySlot` row | that row's status (`open` / `off`) |
| 5 | nothing at all | `open` |

Two consequences worth stating outright:

- **Availability is opt-out, not opt-in.** A therapist who has never touched
  their calendar has no `AvailabilitySlot` rows, so rule 5 makes every slot in
  their working hours `open`. Do not read `open` as "they have positively
  offered this time".
- **Blocks are applied at read time (rule 3).** `POST /availability/block-range`
  — which is also what an admin approving a leave request runs — stamps `off`
  onto the `AvailabilitySlot` rows that exist when it runs. A therapist with no
  rows has nothing to stamp, so until this was fixed their approved leave never
  reached the grid and they read fully `open` to every client. The block rule is
  now re-applied to the synthesised grid on every read, so **a blocked window is
  `off` whether or not a row was ever stored.**

A block covers a slot when its `dateFrom <= date <= dateTo`, **and** its
`daysOfWeek` is empty (meaning every day in the span) or contains that day's
`Sun`/`Mon`/… name, **and** its `partsOfDay` is empty (meaning the whole day) or
contains `full`, or a part whose hours contain the slot's start:
`morning` 06:00–12:00, `afternoon` 12:00–17:00, `evening` 17:00–22:00. This is
the same matching `block_range` writes with — including its exemption for booked
slots, which a block never closes (they surface as cancellations for a human to
confirm instead).

`GET /availability/slots` and `GET /therapists/{id}/slots` still return `blocks`
beside the slots, unchanged. It is not redundant: a per-slot `off` cannot carry
the leave's reason or its span, and the therapist's own calendar in pv-core-web
(`useManageAvailability`) draws its block bands from that array.

---

## 2. `GET /api/v1/availability/slots/bulk`

Answers for many therapists in one request.

**Auth:** `Authorization: Bearer <token>` — required, like every other
availability read. Any authenticated role may ask about any set of therapists.
Note that `GET /therapists` is public but availability is not, so a client
browsing anonymously can list therapists and cannot ask when they are free; that
is deliberate and unchanged.

### Query parameters

| Parameter | Required | Meaning |
|---|---|---|
| `from_date` | yes | `YYYY-MM-DD`, inclusive. |
| `to_date` | yes | `YYYY-MM-DD`, inclusive. Must not precede `from_date`; the window must be **31 days or fewer**. |
| `therapist_ids` | yes in practice | Therapist ids. Repeat the parameter (`?therapist_ids=a&therapist_ids=b`) **or** comma-separate (`?therapist_ids=a,b`) — both work and may be mixed. **At most 50** after de-duplication. Omitting it is legal and returns an empty answer. |
| `status` | no | Which statuses to put in `slots`. `open` (default), `booked`, `off`, or `all`. Repeatable/comma-separated. Does **not** affect `nextFree` or `openCount`. |
| `include_slots` | no | `true` (default) or `false`. `false` returns `slots: []` and keeps `nextFree` and `openCount` — use it for a "next free" line when the full grid is not needed. |

### 200 response

```jsonc
{
  "fromDate": "2030-03-11",
  "toDate": "2030-03-24",
  "therapists": [
    {
      "therapistId": "cuid",
      "slots": [
        { "date": "2030-03-11", "time": "09:00", "status": "open" }
      ],
      "nextFree": { "date": "2030-03-11", "time": "09:00" },
      "openCount": 42
    }
  ],
  "unavailable": [
    { "therapistId": "cuid", "reason": "not_found" }
  ]
}
```

- `therapists` is in **the order the ids were given**, de-duplicated, first
  occurrence winning. Key your map by `therapistId` rather than by position.
- `slots` carries **only** `date`, `time` and `status` — deliberately narrower
  than the single-therapist `SlotInfo`. No `patientName`, `patientPhone`, `fee`
  or `sessionId`: a bulk read is discovery's, and it must not become a way to
  read other patients' booking details out of a therapist's calendar. The
  session's patient relation is not even fetched.
- Slots are ordered by date, then by time.
- `openCount` counts every `open` slot in the window, whatever `status` or
  `include_slots` were set to.
- `nextFree` is the earliest `open` slot **at or after the server's clock**, or
  `null` when there is none in the window. Past slots are still listed in
  `slots` (a caller may be rendering a past week) but are never `nextFree`.
  Times are wall-clock with no offset, as everywhere else in this API; the
  server's clock is the same clock. A client that would rather not trust the
  server's "now" can recompute from `slots`.
- `unavailable` lists ids that were **not answered**, with a reason. It is not
  an error: a 200 with `therapists: []` and a full `unavailable` list is a
  normal response.

| `reason` | Meaning |
|---|---|
| `not_found` | No such therapist, **or** their account is not `APPROVED`. Deliberately one reason for both, so the response discloses nothing about which ids exist — the same policy `GET /therapists/{id}` follows by 404ing for unverified profiles. |
| `not_bookable` | The therapist is `listingType: INFO_ONLY` — a directory entry visited at their clinic, who publishes no slots. This is a real answer, not a failure to look: do not retry it, and do not render it as "could not check". |

A therapist who **is** answered but has nothing open comes back in `therapists`
with `slots: []`, `openCount: 0`, `nextFree: null`. **That is not the same as
`unavailable`**, and the two must render differently: one means "they are busy",
the other means "we have not been told".

### 400 responses

`{"detail": "..."}` for: a malformed `from_date`/`to_date`, `to_date` before
`from_date`, a window longer than 31 days, more than 50 `therapist_ids`, or an
unknown `status`. There is no partial-success 400 — a request either validates
or it does not, and per-therapist problems go to `unavailable`.

### 401

Missing or invalid bearer token.

---

## 3. Notes for the caller

**This replaces the fan-out, not the per-therapist endpoint.** `GET
/availability/slots?therapist_id=` and `GET /therapists/{id}/slots` are
unchanged and remain right for one therapist's full calendar — the profile slot
picker, the booking sheet, the therapist's own management view. Use the bulk
call when the question is about a *list*.

**Pagination lives on `/therapists`, not here.** Page the therapist list as
before and pass the ids of the page you are showing; the 50-id cap sits above
the default page most screens render. This is why the availability filter is not
a parameter on `GET /therapists`: availability is synthesised from a `Setting`
row, slot rows and blocks rather than being a column, so it cannot enter that
endpoint's `where` clause — filtering after the page was taken would make `total`
wrong and hand back short pages, and filtering before it would mean computing
every therapist's calendar on every listing call, public and unauthenticated.

**Cost.** One bulk call is a fixed six queries regardless of how many therapists
it names (therapists, users, working-hours settings, slot rows, sessions,
blocks), against one round trip per therapist before. It performs no writes.

**Sizing the request.** The response is roughly
`therapists × days × slots-per-day` entries when `status=all`. At the default
`status=open` a fully-booked or blocked therapist costs almost nothing. For a
"next free" line on a card, `include_slots=false` is a few dozen bytes per
therapist. Ask for the 14-day discovery horizon rather than the 31-day maximum
unless something needs it.
