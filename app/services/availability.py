import calendar
import json
from datetime import datetime, date, timedelta

from prisma import Prisma

DEFAULT_WORKING_HOURS = {
    "start": "09:00",
    "end": "18:00",
    "slotInterval": 60,
    "sessionDuration": 60,
    "breakDuration": 0,
    "daysOfWeek": ["Mon", "Tue", "Wed", "Thu", "Fri"],
}


def _time_to_minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _session_period(time: str) -> str:
    mins = _time_to_minutes(time)
    if mins < 720:
        return "Morning"
    if mins < 1020:
        return "Afternoon"
    return "Evening"


def _generate_slots(start: str, end: str, interval: int = 120) -> list[str]:
    s, e = _time_to_minutes(start), _time_to_minutes(end)
    return [f"{m // 60:02d}:{m % 60:02d}" for m in range(s, e, interval)]


def _parse_int_list(raw) -> list[int]:
    if isinstance(raw, list):
        return [int(x) for x in raw]
    if isinstance(raw, str):
        return [int(x) for x in json.loads(raw)]
    return []


def _parse_str_list(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        return [str(x) for x in json.loads(raw)]
    return []


def _slot_key(date_str: str, time: str) -> str:
    return f"{date_str}_{time}"


def _is_past(date_str: str, time: str) -> bool:
    try:
        dt = datetime.strptime(f"{date_str} {time}", "%Y-%m-%d %H:%M")
        return dt < datetime.now()
    except ValueError:
        return False


async def _upsert_slot(db: Prisma, therapist_id: str, date_str: str, time: str, status: str):
    existing = await db.availabilityslot.find_first(
        where={"therapistId": therapist_id, "date": date_str, "time": time}
    )
    if existing:
        await db.availabilityslot.update(where={"id": existing.id}, data={"status": status})
    else:
        await db.availabilityslot.create(
            data={"therapistId": therapist_id, "date": date_str, "time": time, "status": status}
        )


async def _find_slot(db: Prisma, therapist_id: str, date_str: str, time: str):
    return await db.availabilityslot.find_first(
        where={"therapistId": therapist_id, "date": date_str, "time": time}
    )


OLD_DEFAULTS = {"start": "08:00", "end": "18:00", "slotInterval": 120}


async def _get_wh(db: Prisma, user_id: str) -> dict:
    row = await db.setting.find_unique(where={"key": f"wh_{user_id}"})
    if row:
        stored = json.loads(row.jsonValue)
        if stored.get("start") == OLD_DEFAULTS["start"] and stored.get("slotInterval") == OLD_DEFAULTS["slotInterval"]:
            merged = {**DEFAULT_WORKING_HOURS}
            await _save_wh(db, user_id, merged)
            return merged
        return {**DEFAULT_WORKING_HOURS, **stored}
    return DEFAULT_WORKING_HOURS.copy()


async def _save_wh(db: Prisma, user_id: str, data: dict) -> dict:
    await db.setting.upsert(
        where={"key": f"wh_{user_id}"},
        data={
            "create": {"key": f"wh_{user_id}", "jsonValue": json.dumps(data)},
            "update": {"jsonValue": json.dumps(data)},
        },
    )
    return data


# ─── SERVICE FUNCTIONS ───


async def get_working_hours(db: Prisma, user_id: str) -> dict:
    return await _get_wh(db, user_id)


async def update_working_hours(db: Prisma, user_id: str, data: dict) -> dict:
    return await _save_wh(db, user_id, data)


async def get_monthly_availability(
    db: Prisma, therapist_id: str, month: int, year: int
) -> dict:
    therapist = await db.therapist.find_unique(where={"id": therapist_id})
    user_id = therapist.userId if therapist and hasattr(therapist, "userId") else therapist_id
    wh = await _get_wh(db, user_id)
    times = _generate_slots(wh["start"], wh["end"], wh.get("sessionDuration", 60) + wh.get("breakDuration", 0))
    days_in_month = calendar.monthrange(year, month)[1]

    rows = await db.availabilityslot.find_many(
        where={"therapistId": therapist_id, "date": {"contains": f"{year}-{month:02d}"}}
    )
    slot_map = {_slot_key(r.date, r.time): r for r in rows}

    month_end = datetime(year, month + 1, 1) if month < 12 else datetime(year + 1, 1, 1)
    sessions = await db.session.find_many(
        where={
            "therapistId": therapist_id,
            "date": {"gte": datetime(year, month, 1), "lt": month_end},
        },
        include={"patient": True},
    )
    session_map = {_slot_key(s.date.strftime("%Y-%m-%d"), s.time): s for s in sessions}

    slots = []
    for d in range(1, days_in_month + 1):
        dk = f"{year}-{month:02d}-{d:02d}"
        for t in times:
            key = _slot_key(dk, t)
            sess = session_map.get(key)
            if sess:
                patient = getattr(sess, "patient", None)
                slots.append({
                    "date": dk, "time": t, "status": "booked",
                    "patientName": patient.name if patient else "",
                    "patientPhone": patient.phone if patient else "",
                    "sessionType": _session_period(t),
                    "fee": sess.fee, "sessionId": sess.id,
                })
            else:
                row = slot_map.get(key)
                slots.append({
                    "date": dk, "time": t,
                    "status": row.status if row else "open",
                    "sessionType": _session_period(t),
                })

    return {"month": f"{year}-{month:02d}", "year": year, "slots": slots}


async def set_slot_status(db: Prisma, therapist_id: str, data: dict) -> None:
    if data["status"] == "booked":
        return
    await _upsert_slot(db, therapist_id, data["date"], data["time"], data["status"])


async def bulk_update_slots(db: Prisma, therapist_id: str, slots: list[dict]) -> int:
    count = 0
    for s in slots:
        if s["status"] == "booked":
            continue
        await _upsert_slot(db, therapist_id, s["date"], s["time"], s["status"])
        count += 1
    return count


async def apply_recurring_pattern(db: Prisma, therapist_id: str, data: dict) -> dict:
    days = data["days"]
    sessions_list = data["sessions"]
    therapist = await db.therapist.find_unique(where={"id": therapist_id})
    user_id = therapist.userId if therapist and hasattr(therapist, "userId") else therapist_id
    wh = await _get_wh(db, user_id)
    now = datetime.now()
    year, month = now.year, now.month
    days_in_month = calendar.monthrange(year, month)[1]
    times = _generate_slots(wh["start"], wh["end"], wh.get("sessionDuration", 60) + wh.get("breakDuration", 0))

    pattern = await db.recurringpattern.create(
        data={"therapistId": therapist_id, "days": json.dumps(days), "sessions": json.dumps(sessions_list)}
    )

    count = skipped = 0
    for d in range(1, days_in_month + 1):
        dt = date(year, month, d)
        if dt.isoweekday() % 7 not in days:
            continue
        dk = f"{year}-{month:02d}-{d:02d}"
        for t in times:
            if _session_period(t) not in sessions_list:
                continue
            if _is_past(dk, t):
                skipped += 1
                continue
            existing = await _find_slot(db, therapist_id, dk, t)
            if existing and existing.status == "booked":
                continue
            await _upsert_slot(db, therapist_id, dk, t, "open")
            count += 1

    return {"affected": count, "skippedPast": skipped, "patternId": pattern.id}


async def get_recurring_patterns(db: Prisma, therapist_id: str) -> list[dict]:
    rows = await db.recurringpattern.find_many(
        where={"therapistId": therapist_id}, order={"createdAt": "desc"}
    )
    return [
        {
            "id": r.id, "therapistId": r.therapistId,
            "days": _parse_int_list(r.days), "sessions": _parse_str_list(r.sessions),
            "isActive": r.isActive, "createdAt": r.createdAt.isoformat(),
        }
        for r in rows
    ]


async def delete_recurring_pattern(db: Prisma, therapist_id: str, pattern_id: str) -> None:
    row = await db.recurringpattern.find_unique(where={"id": pattern_id})
    if not row or row.therapistId != therapist_id:
        return
    await db.recurringpattern.delete(where={"id": pattern_id})


async def toggle_recurring_pattern(
    db: Prisma, therapist_id: str, pattern_id: str, is_active: bool
) -> None:
    row = await db.recurringpattern.find_unique(where={"id": pattern_id})
    if not row or row.therapistId != therapist_id:
        return
    await db.recurringpattern.update(where={"id": pattern_id}, data={"isActive": is_active})


async def apply_schedule(db: Prisma, user_id: str, data: dict) -> dict:
    wh = await _get_wh(db, user_id)
    times = _generate_slots(wh["start"], wh["end"], wh.get("sessionDuration", 60) + wh.get("breakDuration", 0))
    recurrence = data.get("recurrence", "weekly")
    date_from = data.get("dateFrom")
    date_to = data.get("dateTo")

    therapist = await db.therapist.find_unique(where={"userId": user_id})
    if not therapist:
        return {"opened": 0, "skippedBooked": 0, "skippedPast": 0, "from": "", "to": ""}
    therapist_id = therapist.id

    now = datetime.now()

    if recurrence == "weekly":
        start_d = now.date()
        end_d = start_d + timedelta(days=6)
    elif recurrence == "monthly":
        start_d = now.date().replace(day=1)
        next_m = (start_d.month % 12) + 1
        next_y = start_d.year + (1 if next_m == 1 else 0)
        end_d = date(next_y, next_m, 1) - timedelta(days=1)
    elif recurrence == "yearly":
        start_d = now.date().replace(month=1, day=1)
        end_d = date(start_d.year, 12, 31)
    elif recurrence == "range" and date_from and date_to:
        start_d = date.fromisoformat(date_from)
        end_d = date.fromisoformat(date_to)
    else:
        start_d = now.date()
        end_d = start_d + timedelta(days=6)

    opened = skipped_booked = skipped_past = 0
    current = start_d
    while current <= end_d:
        dk = current.strftime("%Y-%m-%d")
        for t in times:
            if _is_past(dk, t):
                skipped_past += 1
                continue
            existing = await _find_slot(db, therapist_id, dk, t)
            if existing and existing.status == "booked":
                skipped_booked += 1
                continue
            await _upsert_slot(db, therapist_id, dk, t, "open")
            opened += 1
        current += timedelta(days=1)

    return {
        "opened": opened,
        "skippedBooked": skipped_booked,
        "skippedPast": skipped_past,
        "from": start_d.isoformat(),
        "to": end_d.isoformat(),
    }


async def open_full_month(db: Prisma, therapist_id: str, data: dict) -> dict:
    year, month = data["year"], data["month"]
    days, sessions_list = data["days"], data["sessions"]
    therapist = await db.therapist.find_unique(where={"id": therapist_id})
    user_id = therapist.userId if therapist and hasattr(therapist, "userId") else therapist_id
    wh = await _get_wh(db, user_id)
    times = _generate_slots(wh["start"], wh["end"], wh.get("sessionDuration", 60) + wh.get("breakDuration", 0))
    days_in_month = calendar.monthrange(year, month)[1]

    opened = skipped_booked = skipped_past = 0
    for d in range(1, days_in_month + 1):
        dt = date(year, month, d)
        if dt.isoweekday() % 7 not in days:
            continue
        dk = f"{year}-{month:02d}-{d:02d}"
        for t in times:
            if _session_period(t) not in sessions_list:
                continue
            if _is_past(dk, t):
                skipped_past += 1
                continue
            existing = await _find_slot(db, therapist_id, dk, t)
            if existing and existing.status == "booked":
                skipped_booked += 1
                continue
            await _upsert_slot(db, therapist_id, dk, t, "open")
            opened += 1

    return {"opened": opened, "skippedBooked": skipped_booked, "skippedPast": skipped_past}


async def block_date(db: Prisma, therapist_id: str, data: dict) -> dict:
    date_str = data["date"]
    sessions_filter = data.get("sessions")
    therapist = await db.therapist.find_unique(where={"id": therapist_id})
    user_id = therapist.userId if therapist and hasattr(therapist, "userId") else therapist_id
    wh = await _get_wh(db, user_id)
    times = _generate_slots(wh["start"], wh["end"], wh.get("sessionDuration", 60) + wh.get("breakDuration", 0))
    blocked = 0

    for t in times:
        if sessions_filter and _session_period(t) not in sessions_filter:
            continue
        existing = await _find_slot(db, therapist_id, date_str, t)
        if existing and existing.status == "booked":
            continue
        await _upsert_slot(db, therapist_id, date_str, t, "off")
        blocked += 1

    return {"blocked": blocked}


# ─── DAY-OF-WEEK HELPERS ───

_DOW_MAP = {"Sun": 0, "Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5, "Sat": 6}

_PARTS_HOURS = {
    "morning": (6, 12),
    "afternoon": (12, 17),
    "evening": (17, 22),
}


def _generate_time_slots(start: str, end: str, session_dur: int, break_dur: int) -> list[str]:
    s = _time_to_minutes(start)
    e = _time_to_minutes(end)
    step = session_dur + break_dur
    return [f"{m // 60:02d}:{m % 60:02d}" for m in range(s, e, step)]


def _slot_in_parts(time_str: str, parts: list[str]) -> bool:
    if "full" in parts:
        return True
    hour = _time_to_minutes(time_str) // 60
    for part in parts:
        bounds = _PARTS_HOURS.get(part)
        if bounds and bounds[0] <= hour < bounds[1]:
            return True
    return False


def _parse_json_list(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        return [str(x) for x in json.loads(raw)]
    return []


# ─── SERVICE FUNCTIONS ───


async def generate_availability(db: Prisma, therapist_id: str, data: dict) -> dict:
    date_from = date.fromisoformat(data["dateFrom"])
    date_to = date.fromisoformat(data["dateTo"]) if data.get("dateTo") else date_from + timedelta(days=365)
    selected_dows = {_DOW_MAP[d] for d in data["daysOfWeek"] if d in _DOW_MAP}
    times = _generate_time_slots(data["startTime"], data["endTime"], data["sessionDuration"], data["breakDuration"])

    opened = 0
    offed = 0
    current = date_from
    while current <= date_to:
        dk = current.strftime("%Y-%m-%d")
        is_selected = current.isoweekday() % 7 in selected_dows
        for t in times:
            if _is_past(dk, t):
                continue
            existing = await _find_slot(db, therapist_id, dk, t)
            if is_selected:
                if existing and existing.status == "booked":
                    continue
                await _upsert_slot(db, therapist_id, dk, t, "open")
                opened += 1
            else:
                if existing and existing.status == "booked":
                    continue
                await _upsert_slot(db, therapist_id, dk, t, "off")
                offed += 1
        current += timedelta(days=1)

    wh_data = {
        "start": data["startTime"],
        "end": data["endTime"],
        "slotInterval": data["sessionDuration"],
        "sessionDuration": data["sessionDuration"],
        "breakDuration": data["breakDuration"],
        "daysOfWeek": data.get("daysOfWeek", []),
    }
    therapist = await db.therapist.find_unique(where={"id": therapist_id})
    user_id = therapist.userId if therapist and hasattr(therapist, "userId") else therapist_id
    await _save_wh(db, user_id, wh_data)

    return {"updated": opened}


async def block_range(db: Prisma, therapist_id: str, data: dict) -> dict:
    date_from = date.fromisoformat(data["dateFrom"])
    raw_date_to = data.get("dateTo")
    date_to = date.fromisoformat(raw_date_to) if raw_date_to else date_from
    raw_dows = data.get("daysOfWeek", [])
    selected_dows = {_DOW_MAP[d] for d in raw_dows if d in _DOW_MAP}
    parts = data.get("partsOfDay", [])

    block = await db.availabilityblock.create(
        data={
            "therapistId": therapist_id,
            "dateFrom": data["dateFrom"],
            "dateTo": raw_date_to if raw_date_to else data["dateFrom"],
            "daysOfWeek": json.dumps(raw_dows),
            "partsOfDay": json.dumps(parts),
            "reason": data.get("reason", ""),
            "notify": data.get("notify", False),
        }
    )

    blocked = 0
    cancelled_count = 0
    affected_patients: list[str] = []
    current = date_from
    match_all_dows = len(selected_dows) == 0
    match_all_parts = len(parts) == 0

    while current <= date_to:
        if match_all_dows or (current.isoweekday() % 7 in selected_dows):
            dk = current.strftime("%Y-%m-%d")
            rows = await db.availabilityslot.find_many(
                where={"therapistId": therapist_id, "date": dk}
            )
            for row in rows:
                if not match_all_parts and not _slot_in_parts(row.time, parts):
                    continue
                if row.status == "booked":
                    sess = await db.session.find_first(
                        where={
                            "therapistId": therapist_id,
                            "date": datetime.strptime(dk, "%Y-%m-%d"),
                            "time": row.time,
                        },
                        include={"patient": True},
                    )
                    if sess:
                        patient = getattr(sess, "patient", None)
                        if patient and patient.name not in affected_patients:
                            affected_patients.append(patient.name)
                        cancelled_count += 1
                    continue
                if _is_past(dk, row.time):
                    continue
                await _upsert_slot(db, therapist_id, dk, row.time, "off")
                blocked += 1
        current += timedelta(days=1)

    block_type = data.get("blockType", "range")
    await db.auditlogentry.create(
        data={
            "therapistId": therapist_id,
            "date": data["dateFrom"],
            "reason": data["reason"],
            "scope": block_type,
            "source": "block_range",
            "blockId": block.id,
        }
    )

    return {
        "blocked": blocked,
        "cancelledCount": cancelled_count,
        "affectedPatients": affected_patients,
    }


async def unblock_item(db: Prisma, therapist_id: str, date_str: str, time: str | None = None) -> dict:
    if time:
        slot = await _find_slot(db, therapist_id, date_str, time)
        if slot and slot.status == "off" and not _is_past(date_str, time):
            await _upsert_slot(db, therapist_id, date_str, time, "open")
        return {"success": True}

    rows = await db.availabilityslot.find_many(
        where={"therapistId": therapist_id, "date": date_str, "status": "off"}
    )
    for row in rows:
        if not _is_past(date_str, row.time):
            await _upsert_slot(db, therapist_id, date_str, row.time, "open")

    await db.auditlogentry.delete_many(
        where={"therapistId": therapist_id, "date": date_str}
    )

    await db.availabilityblock.delete_many(
        where={
            "therapistId": therapist_id,
            "dateFrom": {"lte": date_str},
            "dateTo": {"gte": date_str},
        }
    )

    return {"success": True}


async def get_slots_for_range(db: Prisma, therapist_id: str, date_from: str, date_to: str) -> dict:
    d_from = date.fromisoformat(date_from)
    d_to = date.fromisoformat(date_to)

    therapist = await db.therapist.find_unique(where={"id": therapist_id})
    user_id = therapist.userId if therapist and hasattr(therapist, "userId") else therapist_id
    wh = await _get_wh(db, user_id)
    times = _generate_slots(wh["start"], wh["end"], wh.get("sessionDuration", 60) + wh.get("breakDuration", 0))

    slot_rows = await db.availabilityslot.find_many(
        where={
            "therapistId": therapist_id,
            "date": {"gte": date_from, "lte": date_to},
        }
    )
    slot_map = {_slot_key(r.date, r.time): r for r in slot_rows}

    sessions = await db.session.find_many(
        where={
            "therapistId": therapist_id,
            "date": {
                "gte": datetime.combine(d_from, datetime.min.time()),
                "lte": datetime.combine(d_to, datetime.max.time()),
            },
        },
        include={"patient": True},
    )
    session_map = {_slot_key(s.date.strftime("%Y-%m-%d"), s.time): s for s in sessions}

    block_rows = await db.availabilityblock.find_many(
        where={
            "therapistId": therapist_id,
            "dateFrom": {"lte": date_to},
            "OR": [
                {"dateTo": {"gte": date_from}},
                {"dateTo": {"gte": date_from}},
            ],
        }
    )

    slots: list[dict] = []
    current = d_from
    while current <= d_to:
        dk = current.strftime("%Y-%m-%d")
        for t in times:
            key = _slot_key(dk, t)
            sess = session_map.get(key)
            if sess:
                patient = getattr(sess, "patient", None)
                slots.append({
                    "date": dk,
                    "time": t,
                    "status": "booked",
                    "patientName": patient.name if patient else "",
                    "patientPhone": patient.phone if patient else "",
                    "sessionType": _session_period(t),
                    "fee": sess.fee,
                    "sessionId": sess.id,
                })
            else:
                row = slot_map.get(key)
                slots.append({
                    "date": dk,
                    "time": t,
                    "status": row.status if row else "open",
                    "sessionType": _session_period(t),
                })
        current += timedelta(days=1)

    blocks = [
        {
            "id": b.id,
            "dateFrom": b.dateFrom,
            "dateTo": b.dateTo,
            "daysOfWeek": _parse_json_list(b.daysOfWeek),
            "partsOfDay": _parse_json_list(b.partsOfDay),
            "reason": b.reason,
            "notify": b.notify,
            "createdAt": b.createdAt.isoformat(),
        }
        for b in block_rows
    ]

    return {"slots": slots, "blocks": blocks}


async def get_working_days(db: Prisma, therapist_id: str) -> list[str]:
    rows = await db.availabilityslot.find_many(
        where={"therapistId": therapist_id},
        distinct=["date"],
    )
    dow_names = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
    days_set: set[str] = set()
    for row in rows:
        try:
            d = date.fromisoformat(row.date)
            days_set.add(dow_names[d.isoweekday() % 7])
        except ValueError:
            continue
    return sorted(days_set, key=lambda x: list(dow_names.values()).index(x))


async def get_audit_entries(db: Prisma, therapist_id: str, limit: int = 5, offset: int = 0) -> dict:
    where = {"therapistId": therapist_id}
    total = await db.auditlogentry.count(where=where)
    rows = await db.auditlogentry.find_many(
        where=where,
        order={"createdAt": "desc"},
        take=limit,
        skip=offset,
        include={"block": True},
    )
    entries = [
        {
            "id": r.id,
            "date": r.date,
            "time": r.time,
            "reason": r.reason,
            "scope": r.scope,
            "source": r.source,
            "createdAt": r.createdAt.isoformat(),
            "dateTo": r.block.dateTo if r.block else None,
            "daysOfWeek": _parse_json_list(r.block.daysOfWeek) if r.block and r.block.daysOfWeek else [],
            "partsOfDay": _parse_json_list(r.block.partsOfDay) if r.block and r.block.partsOfDay else [],
        }
        for r in rows
    ]
    return {"entries": entries, "total": total}


async def create_audit_entry(db: Prisma, therapist_id: str, data: dict) -> dict:
    row = await db.auditlogentry.create(
        data={
            "therapistId": therapist_id,
            "date": data["date"],
            "time": data.get("time"),
            "reason": data["reason"],
            "scope": data["scope"],
            "source": data["source"],
            "blockId": data.get("blockId"),
        }
    )
    return {
        "id": row.id,
        "date": row.date,
        "time": row.time,
        "reason": row.reason,
        "scope": row.scope,
        "source": row.source,
        "createdAt": row.createdAt.isoformat(),
    }


async def delete_audit_entry(db: Prisma, therapist_id: str, entry_id: str) -> None:
    row = await db.auditlogentry.find_unique(where={"id": entry_id})
    if not row or row.therapistId != therapist_id:
        return
    await db.auditlogentry.delete(where={"id": entry_id})


# ─── BLOCK REQUEST SERVICE FUNCTIONS ───


async def create_block_request(db: Prisma, therapist_id: str, data: dict) -> dict:
    date_from = date.fromisoformat(data["dateFrom"])
    date_to = date.fromisoformat(data["dateTo"]) if data.get("dateTo") else date_from
    raw_dows = data.get("daysOfWeek", [])
    parts = data.get("partsOfDay", [])

    request = await db.scheduleblockrequest.create(
        data={
            "therapistId": therapist_id,
            "dateFrom": data["dateFrom"],
            "dateTo": (data.get("dateTo") or data["dateFrom"]),
            "daysOfWeek": json.dumps(raw_dows),
            "partsOfDay": json.dumps(parts),
            "reason": data.get("reason", ""),
            "notify": data.get("notify", False),
            "status": "PENDING",
        }
    )

    return {
        "id": request.id,
        "dateFrom": request.dateFrom,
        "dateTo": request.dateTo,
        "status": request.status,
        "createdAt": request.createdAt.isoformat(),
    }


async def get_pending_block_requests(db: Prisma) -> list[dict]:
    rows = await db.scheduleblockrequest.find_many(
        where={"status": "PENDING"},
        order={"createdAt": "desc"},
    )
    result = []
    for r in rows:
        therapist = await db.therapist.find_unique(where={"id": r.therapistId})
        user = await db.user.find_unique(where={"id": therapist.userId}) if therapist and hasattr(therapist, "userId") else None
        result.append({
            "id": r.id,
            "therapistId": r.therapistId,
            "therapistName": therapist.name if therapist else "",
            "therapistEmail": user.email if user else "",
            "dateFrom": r.dateFrom,
            "dateTo": r.dateTo,
            "daysOfWeek": _parse_json_list(r.daysOfWeek),
            "partsOfDay": _parse_json_list(r.partsOfDay),
            "reason": r.reason,
            "notify": r.notify,
            "status": r.status,
            "createdAt": r.createdAt.isoformat(),
        })
    return result


async def get_therapist_block_requests(db: Prisma, therapist_id: str) -> list[dict]:
    rows = await db.scheduleblockrequest.find_many(
        where={"therapistId": therapist_id},
        order={"createdAt": "desc"},
        take=20,
    )
    return [
        {
            "id": r.id,
            "dateFrom": r.dateFrom,
            "dateTo": r.dateTo,
            "daysOfWeek": _parse_json_list(r.daysOfWeek),
            "partsOfDay": _parse_json_list(r.partsOfDay),
            "reason": r.reason,
            "status": r.status,
            "adminNotes": r.adminNotes,
            "createdAt": r.createdAt.isoformat(),
        }
        for r in rows
    ]


async def approve_block_request(db: Prisma, request_id: str, admin_notes: str = "") -> dict:
    request = await db.scheduleblockrequest.find_unique(where={"id": request_id})
    if not request:
        return {"success": False, "error": "Request not found"}

    await db.scheduleblockrequest.update(
        where={"id": request_id},
        data={"status": "APPROVED", "adminNotes": admin_notes},
    )

    block_data = {
        "dateFrom": request.dateFrom,
        "dateTo": request.dateTo,
        "daysOfWeek": _parse_json_list(request.daysOfWeek),
        "partsOfDay": _parse_json_list(request.partsOfDay),
        "reason": request.reason,
        "notify": request.notify,
    }
    result = await block_range(db, request.therapistId, block_data)

    return {
        "success": True,
        "blocked": result["blocked"],
        "cancelledCount": result["cancelledCount"],
        "affectedPatients": result["affectedPatients"],
    }


async def reject_block_request(db: Prisma, request_id: str, admin_notes: str = "") -> dict:
    request = await db.scheduleblockrequest.find_unique(where={"id": request_id})
    if not request:
        return {"success": False, "error": "Request not found"}

    await db.scheduleblockrequest.update(
        where={"id": request_id},
        data={"status": "REJECTED", "adminNotes": admin_notes},
    )

    return {"success": True}
