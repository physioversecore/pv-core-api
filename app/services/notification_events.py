"""Producers for the per-user notification feed.

`user_notification.py` is the storage layer -- create, list, mark read. This
module is the *event* layer: one function per thing that actually happens in
the product, each deciding who hears about it and in what words.

Three rules hold throughout:

* **The type registry is a contract.** ``NotificationType`` is the complete set
  of keys a client may switch on, and ``RefType`` the complete set of things a
  notification can point at. Adding a key is additive; renaming one breaks
  every installed app. Documented in ``docs/notification_types.md``.

* **A notification never breaks the request that caused it.** Every write goes
  through ``safe_notify``, which swallows and logs, mirroring
  ``app/services/email/dispatch.py``. Routers schedule these through FastAPI
  ``BackgroundTasks`` so the round-trip is off the response path as well. A
  booking must not 500 because an insert failed.

* **Decisions are announced once.** ``notify_once`` refuses to write a second
  row with the same (user, type, refId), so a retried admin approval or a
  re-saved session status cannot stack duplicates in someone's feed. Events
  that can genuinely recur for the same subject -- a session rescheduled twice
  -- deliberately use ``safe_notify`` instead.

Recipients are *users*. A session carries a `therapistId` pointing at the
Therapist profile, not at a User, so every therapist-facing producer resolves
`therapist.userId` before writing.
"""

import logging
from enum import StrEnum
from types import SimpleNamespace

from prisma import Prisma

from app.services.user_notification import create_notification

logger = logging.getLogger(__name__)


class NotificationType(StrEnum):
    """Every key the feed can carry. See docs/notification_types.md."""

    # -- Bookings --
    SESSION_BOOKED = "SESSION_BOOKED"
    SESSION_NEW_BOOKING = "SESSION_NEW_BOOKING"
    SESSION_RESCHEDULED = "SESSION_RESCHEDULED"
    SESSION_RESCHEDULE_REQUESTED = "SESSION_RESCHEDULE_REQUESTED"
    SESSION_DECLINE_REQUESTED = "SESSION_DECLINE_REQUESTED"
    SESSION_CANCELLED = "SESSION_CANCELLED"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_RATE_REQUEST = "SESSION_RATE_REQUEST"

    # -- Money --
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    REFUND_REQUESTED = "REFUND_REQUESTED"
    REFUND_APPROVED = "REFUND_APPROVED"
    REFUND_DENIED = "REFUND_DENIED"

    # -- Therapist lifecycle --
    APPLICATION_APPROVED = "APPLICATION_APPROVED"
    APPLICATION_REJECTED = "APPLICATION_REJECTED"
    RATE_CHANGE_APPROVED = "RATE_CHANGE_APPROVED"
    RATE_CHANGE_REJECTED = "RATE_CHANGE_REJECTED"
    LEAVE_APPROVED = "LEAVE_APPROVED"
    LEAVE_REJECTED = "LEAVE_REJECTED"

    # -- Care record --
    REPORT_UPLOADED = "REPORT_UPLOADED"

    # -- Rewards --
    REFERRAL_JOINED = "REFERRAL_JOINED"
    REFERRAL_REWARDED = "REFERRAL_REWARDED"
    POINTS_MATURED = "POINTS_MATURED"


class RefType(StrEnum):
    """What `refId` names, so a client knows which screen to deep-link to."""

    SESSION = "SESSION"
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    REPORT = "REPORT"
    THERAPIST = "THERAPIST"
    RATE_CHANGE = "RATE_CHANGE"
    LEAVE = "LEAVE"
    REFERRAL = "REFERRAL"
    POINTS = "POINTS"


# ── Writing ────────────────────────────────────────────────────────────────


async def safe_notify(
    db: Prisma,
    user_id: str | None,
    *,
    type: NotificationType | str,
    title: str,
    body: str,
    ref_type: RefType | str | None = None,
    ref_id: str | None = None,
) -> None:
    """Write one notification, swallowing every failure.

    The feed is secondary to whatever the user was actually doing. A missing
    recipient (an unresolved therapist profile, say) is a no-op rather than an
    error, for the same reason.
    """
    if not user_id:
        return
    try:
        await create_notification(
            db,
            user_id,
            type=str(type),
            title=title,
            body=body,
            ref_type=str(ref_type) if ref_type else None,
            ref_id=ref_id,
        )
    except Exception:
        logger.exception(
            "Notification write failed",
            extra={"userId": user_id, "type": str(type), "refId": ref_id},
        )


async def notify_once(
    db: Prisma,
    user_id: str | None,
    *,
    type: NotificationType | str,
    title: str,
    body: str,
    ref_type: RefType | str | None = None,
    ref_id: str | None = None,
) -> None:
    """`safe_notify`, but skip if this exact event was already announced.

    The guard is (userId, type, refId): a retried approval, a re-saved session
    status, or a second call from a client that did not get the first response
    all resolve to the same triple. Without `ref_id` there is no key to dedupe
    on, so it degrades to `safe_notify`.
    """
    if not user_id:
        return
    if ref_id:
        try:
            existing = await db.notification.find_first(
                where={"userId": user_id, "type": str(type), "refId": ref_id}
            )
            if existing:
                return
        except Exception:
            # A failed dedupe check must not cost the user the notification.
            logger.exception(
                "Notification dedupe check failed; writing anyway",
                extra={"userId": user_id, "type": str(type), "refId": ref_id},
            )
    await safe_notify(
        db,
        user_id,
        type=type,
        title=title,
        body=body,
        ref_type=ref_type,
        ref_id=ref_id,
    )


# ── Copy helpers ───────────────────────────────────────────────────────────


def _first_name(name: str | None) -> str:
    return (name or "").split()[0] if name else ""


def _npr(amount) -> str:
    """`Rs 1,500` -- matching how money is written everywhere else."""
    try:
        return "Rs {:,.0f}".format(float(amount))
    except (TypeError, ValueError):
        return "Rs 0"


def _when(date_value, time_value) -> str:
    """`Sat, 14 Jun at 10:00` -- the two facts a patient needs to plan around."""
    parts = []
    try:
        parts.append(
            "{}, {} {}".format(
                date_value.strftime("%a"), date_value.day, date_value.strftime("%b")
            )
        )
    except AttributeError:
        if date_value:
            parts.append(str(date_value)[:10])
    if time_value:
        parts.append("at {}".format(time_value))
    return " ".join(parts) if parts else "the scheduled time"


def _visit_verb(session_type: str | None) -> str:
    """Home visits come to you; everything else you go to."""
    return "will visit you" if (session_type or "") == "HOME_VISIT" else "will see you"


async def _session_context(db: Prisma, session_id: str):
    """Both parties, both names and the human time, from one read.

    Producers resolve their own copy from the database rather than trusting
    whatever the caller happened to have in hand: the router's session dict is
    shaped differently on every path, and a notification that names the wrong
    person is worse than none.
    """
    try:
        session = await db.session.find_unique(
            where={"id": session_id},
            include={"therapist": True, "patient": True},
        )
    except Exception:
        logger.exception("Session lookup for notification failed")
        return None
    if not session:
        return None

    therapist = getattr(session, "therapist", None)
    patient = getattr(session, "patient", None)
    return SimpleNamespace(
        session=session,
        session_id=session_id,
        patient_user_id=getattr(session, "patientId", None),
        therapist_id=getattr(session, "therapistId", None),
        therapist_user_id=getattr(therapist, "userId", None),
        patient_name=getattr(patient, "name", None) or "Your patient",
        therapist_name=getattr(therapist, "name", None) or "Your therapist",
        when=_when(getattr(session, "date", None), getattr(session, "time", None)),
        verb=_visit_verb(getattr(session, "type", None)),
        fee=getattr(session, "fee", 0),
    )


async def _therapist_user_id(db: Prisma, therapist_id: str | None) -> str | None:
    if not therapist_id:
        return None
    try:
        therapist = await db.therapist.find_unique(where={"id": therapist_id})
    except Exception:
        logger.exception("Therapist lookup for notification failed")
        return None
    return getattr(therapist, "userId", None) if therapist else None


# ── Bookings ───────────────────────────────────────────────────────────────


async def notify_session_booked(db: Prisma, session_id: str) -> None:
    """A slot was booked. Both sides hear it, each in their own words."""
    ctx = await _session_context(db, session_id)
    if not ctx:
        return

    await notify_once(
        db,
        ctx.patient_user_id,
        type=NotificationType.SESSION_BOOKED,
        title="Booking confirmed",
        body="{} {} on {}.".format(ctx.therapist_name, ctx.verb, ctx.when),
        ref_type=RefType.SESSION,
        ref_id=session_id,
    )
    await notify_once(
        db,
        ctx.therapist_user_id,
        type=NotificationType.SESSION_NEW_BOOKING,
        title="New booking",
        body="{} booked you for {}.".format(ctx.patient_name, ctx.when),
        ref_type=RefType.SESSION,
        ref_id=session_id,
    )


async def notify_session_rescheduled(db: Prisma, session_id: str) -> None:
    """The patient moved the slot themselves; the therapist's day changed.

    Deliberately not `notify_once`: a session can legitimately be moved more
    than once, and each move is news.
    """
    ctx = await _session_context(db, session_id)
    if not ctx:
        return

    await safe_notify(
        db,
        ctx.patient_user_id,
        type=NotificationType.SESSION_RESCHEDULED,
        title="Session moved",
        body="Your session with {} is now on {}.".format(
            ctx.therapist_name, ctx.when
        ),
        ref_type=RefType.SESSION,
        ref_id=session_id,
    )
    await safe_notify(
        db,
        ctx.therapist_user_id,
        type=NotificationType.SESSION_RESCHEDULED,
        title="Session moved",
        body="{} moved their session to {}.".format(ctx.patient_name, ctx.when),
        ref_type=RefType.SESSION,
        ref_id=session_id,
    )


async def notify_reschedule_requested(
    db: Prisma, session_id: str, *, actor_user_id: str | None = None
) -> None:
    """One side asked to move the slot. The other side has to answer."""
    ctx = await _session_context(db, session_id)
    if not ctx:
        return

    if actor_user_id and actor_user_id == ctx.therapist_user_id:
        await safe_notify(
            db,
            ctx.patient_user_id,
            type=NotificationType.SESSION_RESCHEDULE_REQUESTED,
            title="Reschedule requested",
            body="{} has asked to move your {} session. We will confirm a new "
            "time with you shortly.".format(ctx.therapist_name, ctx.when),
            ref_type=RefType.SESSION,
            ref_id=session_id,
        )
        return

    await safe_notify(
        db,
        ctx.therapist_user_id,
        type=NotificationType.SESSION_RESCHEDULE_REQUESTED,
        title="Reschedule requested",
        body="{} has asked to move the {} session.".format(
            ctx.patient_name, ctx.when
        ),
        ref_type=RefType.SESSION,
        ref_id=session_id,
    )


async def notify_decline_requested(db: Prisma, session_id: str) -> None:
    """The therapist asked to hand a session back.

    Only the therapist is told, and only that the request is in. The patient
    hears nothing until the decision actually lands as a cancellation --
    telling them their visit *might* fall through helps no one.
    """
    ctx = await _session_context(db, session_id)
    if not ctx:
        return

    await safe_notify(
        db,
        ctx.therapist_user_id,
        type=NotificationType.SESSION_DECLINE_REQUESTED,
        title="Decline request sent",
        body="We have your request to decline the {} session with {}. Our team "
        "will confirm before the patient is told.".format(ctx.when, ctx.patient_name),
        ref_type=RefType.SESSION,
        ref_id=session_id,
    )


async def notify_session_cancelled(
    db: Prisma, session_id: str, *, actor_user_id: str | None = None
) -> None:
    """A session is off. Both sides hear it, and who did it is in the words."""
    ctx = await _session_context(db, session_id)
    if not ctx:
        return

    if actor_user_id and actor_user_id == ctx.patient_user_id:
        patient_body = "You cancelled your {} session with {}.".format(
            ctx.when, ctx.therapist_name
        )
        therapist_body = "{} cancelled the {} session.".format(
            ctx.patient_name, ctx.when
        )
    elif actor_user_id and actor_user_id == ctx.therapist_user_id:
        patient_body = (
            "{} cancelled your {} session. You can book another time from the "
            "app.".format(ctx.therapist_name, ctx.when)
        )
        therapist_body = "You cancelled the {} session with {}.".format(
            ctx.when, ctx.patient_name
        )
    else:
        patient_body = (
            "Your {} session with {} was cancelled by our team. You can book "
            "another time from the app.".format(ctx.when, ctx.therapist_name)
        )
        therapist_body = "The {} session with {} was cancelled by our team.".format(
            ctx.when, ctx.patient_name
        )

    await notify_once(
        db,
        ctx.patient_user_id,
        type=NotificationType.SESSION_CANCELLED,
        title="Session cancelled",
        body=patient_body,
        ref_type=RefType.SESSION,
        ref_id=session_id,
    )
    await notify_once(
        db,
        ctx.therapist_user_id,
        type=NotificationType.SESSION_CANCELLED,
        title="Session cancelled",
        body=therapist_body,
        ref_type=RefType.SESSION,
        ref_id=session_id,
    )


async def _can_still_review(db: Prisma, patient_user_id, therapist_id) -> bool:
    """A rating prompt is only honest while the rating screen would accept it.

    `POST /reviews` rejects a second review of the same therapist, so asking
    again would send the patient to a dead end.
    """
    if not patient_user_id or not therapist_id:
        return False
    try:
        existing = await db.review.find_first(
            where={"patientId": patient_user_id, "therapistId": therapist_id}
        )
    except Exception:
        logger.exception("Review lookup for notification failed")
        return False
    return existing is None


async def notify_session_completed(db: Prisma, session_id: str) -> None:
    """A visit is done.

    The therapist gets a completion record. The patient gets the rating prompt
    the design asks for -- but only while a review is still possible; once they
    have already rated this therapist they get the plain completion instead.
    """
    ctx = await _session_context(db, session_id)
    if not ctx:
        return

    await notify_once(
        db,
        ctx.therapist_user_id,
        type=NotificationType.SESSION_COMPLETED,
        title="Session completed",
        body="Your {} session with {} is marked complete. {} has been added to "
        "your earnings.".format(ctx.when, ctx.patient_name, _npr(ctx.fee)),
        ref_type=RefType.SESSION,
        ref_id=session_id,
    )

    if await _can_still_review(db, ctx.patient_user_id, ctx.therapist_id):
        await notify_once(
            db,
            ctx.patient_user_id,
            type=NotificationType.SESSION_RATE_REQUEST,
            title="Rate your last session",
            body="How was your session with {}? Your rating helps other "
            "patients choose.".format(ctx.therapist_name),
            ref_type=RefType.SESSION,
            ref_id=session_id,
        )
        return

    await notify_once(
        db,
        ctx.patient_user_id,
        type=NotificationType.SESSION_COMPLETED,
        title="Session completed",
        body="Your {} session with {} is complete. Take care and rest well.".format(
            ctx.when, ctx.therapist_name
        ),
        ref_type=RefType.SESSION,
        ref_id=session_id,
    )


async def notify_session_status_change(
    db: Prisma,
    session_id: str,
    *,
    new_status: str,
    previous_status: str | None = None,
    actor_user_id: str | None = None,
) -> None:
    """Fan a session status write out to whichever producer it belongs to.

    Nothing fires unless the status actually moved: `PUT /sessions/{id}` is
    used for note and time edits too, and a client that re-saves the same
    status must not re-announce it.
    """
    if not new_status or new_status == previous_status:
        return

    if new_status == "CANCELLED":
        await notify_session_cancelled(db, session_id, actor_user_id=actor_user_id)
    elif new_status == "COMPLETED":
        await notify_session_completed(db, session_id)
    elif new_status == "RESCHEDULE_REQUESTED":
        await notify_reschedule_requested(
            db, session_id, actor_user_id=actor_user_id
        )
    elif new_status == "DECLINE_REQUESTED":
        await notify_decline_requested(db, session_id)
    # SCHEDULED and IN_PROGRESS are deliberately silent: the first is the
    # state a booking is already announced in, and the second happens with the
    # therapist standing in the patient's front room.


# ── Money ──────────────────────────────────────────────────────────────────


def _method_label(method: str | None) -> str:
    """`KHALTI` -> `Khalti`, `BANK_TRANSFER` -> `Bank transfer`."""
    raw = (method or "").replace("_", " ").strip()
    return raw.capitalize() if raw else "Your"


async def notify_payment_received(db: Prisma, payment_id: str) -> None:
    """A payment settled. Only the payer hears it."""
    try:
        payment = await db.payment.find_unique(where={"id": payment_id})
    except Exception:
        logger.exception("Payment lookup for notification failed")
        return
    if not payment:
        return

    body = "{} payment of {} confirmed.".format(
        _method_label(getattr(payment, "method", None)),
        _npr(getattr(payment, "amount", 0)),
    )
    session_id = getattr(payment, "sessionId", None)
    if session_id:
        ctx = await _session_context(db, session_id)
        if ctx:
            body = "{} payment of {} confirmed. {} {} on {}.".format(
                _method_label(getattr(payment, "method", None)),
                _npr(getattr(payment, "amount", 0)),
                ctx.therapist_name,
                ctx.verb,
                ctx.when,
            )

    await notify_once(
        db,
        getattr(payment, "userId", None),
        type=NotificationType.PAYMENT_RECEIVED,
        title="Payment received",
        body=body,
        ref_type=RefType.PAYMENT,
        ref_id=payment_id,
    )


async def notify_refund_opened(
    db: Prisma, refund_id: str, *, patient_user_id: str, amount, booking_id: str = ""
) -> None:
    """A refund case was opened on the patient's booking."""
    where = " for booking {}".format(booking_id) if booking_id else ""
    await notify_once(
        db,
        patient_user_id,
        type=NotificationType.REFUND_REQUESTED,
        title="Refund request received",
        body="We have opened a refund request of {}{}. Our team will review it "
        "and get back to you.".format(_npr(amount), where),
        ref_type=RefType.REFUND,
        ref_id=refund_id,
    )


async def notify_refund_decided(
    db: Prisma,
    refund_id: str,
    *,
    patient_user_id: str,
    decision: str,
    amount,
    deny_reason: str | None = None,
) -> None:
    """A refund was approved or denied. Denials carry the reason."""
    if decision == "APPROVED":
        await notify_once(
            db,
            patient_user_id,
            type=NotificationType.REFUND_APPROVED,
            title="Refund approved",
            body="Your refund of {} is approved. It will reach your original "
            "payment method within a few working days.".format(_npr(amount)),
            ref_type=RefType.REFUND,
            ref_id=refund_id,
        )
        return

    reason = (deny_reason or "").strip()
    tail = " Reason: {}".format(reason) if reason else ""
    await notify_once(
        db,
        patient_user_id,
        type=NotificationType.REFUND_DENIED,
        title="Refund not approved",
        body="We could not approve your refund of {}.{} Contact support if you "
        "would like us to look again.".format(_npr(amount), tail),
        ref_type=RefType.REFUND,
        ref_id=refund_id,
    )


# ── Therapist lifecycle ────────────────────────────────────────────────────


async def notify_application_decided(
    db: Prisma,
    *,
    user_id: str,
    user_name: str = "",
    therapist_id: str | None = None,
    approved: bool,
    note: str | None = None,
) -> None:
    """The in-app twin of the approval/rejection emails.

    A rejected therapist cannot sign in, so in practice only the approval is
    ever read in the app. The rejection row is still written: it is the record
    that shows up if the account is later approved, and the email carries the
    message in the meantime.
    """
    name = _first_name(user_name)
    greeting = "{}, y".format(name) if name else "Y"

    if approved:
        await notify_once(
            db,
            user_id,
            type=NotificationType.APPLICATION_APPROVED,
            title="You are verified",
            body="{}our therapist account is approved. Set your availability "
            "and you will start receiving bookings.".format(greeting),
            ref_type=RefType.THERAPIST,
            ref_id=therapist_id,
        )
        return

    reason = (note or "").strip()
    tail = " Reason: {}".format(reason) if reason else ""
    await notify_once(
        db,
        user_id,
        type=NotificationType.APPLICATION_REJECTED,
        title="Update on your application",
        body="{}our therapist application was not approved.{} You can reapply "
        "with updated documents once the issue is resolved.".format(greeting, tail),
        ref_type=RefType.THERAPIST,
        ref_id=therapist_id,
    )


async def notify_rate_change_decided(
    db: Prisma,
    request_id: str,
    *,
    therapist_id: str,
    approved: bool,
    new_rate=None,
    admin_notes: str | None = None,
) -> None:
    """A session-rate change request was decided."""
    user_id = await _therapist_user_id(db, therapist_id)
    if not user_id:
        return

    if approved:
        await notify_once(
            db,
            user_id,
            type=NotificationType.RATE_CHANGE_APPROVED,
            title="New rate approved",
            body="Your session rate is now {}. New bookings will be charged at "
            "this rate.".format(_npr(new_rate)),
            ref_type=RefType.RATE_CHANGE,
            ref_id=request_id,
        )
        return

    notes = (admin_notes or "").strip()
    tail = " Reason: {}".format(notes) if notes else ""
    await notify_once(
        db,
        user_id,
        type=NotificationType.RATE_CHANGE_REJECTED,
        title="Rate change not approved",
        body="Your rate change request was not approved.{} Your current rate "
        "stays as it is.".format(tail),
        ref_type=RefType.RATE_CHANGE,
        ref_id=request_id,
    )


async def notify_block_request_decided(
    db: Prisma,
    request_id: str,
    *,
    therapist_id: str,
    approved: bool,
    date_from: str = "",
    date_to: str = "",
    admin_notes: str | None = None,
) -> None:
    """A time-off request was approved or rejected."""
    user_id = await _therapist_user_id(db, therapist_id)
    if not user_id:
        return

    if date_from and date_to and date_from != date_to:
        span = "{} to {}".format(date_from, date_to)
    else:
        span = date_from or "the requested dates"

    if approved:
        await notify_once(
            db,
            user_id,
            type=NotificationType.LEAVE_APPROVED,
            title="Time off approved",
            body="Your time off for {} is approved. Those slots are now closed "
            "to new bookings.".format(span),
            ref_type=RefType.LEAVE,
            ref_id=request_id,
        )
        return

    notes = (admin_notes or "").strip()
    tail = " Reason: {}".format(notes) if notes else ""
    await notify_once(
        db,
        user_id,
        type=NotificationType.LEAVE_REJECTED,
        title="Time off not approved",
        body="Your time off request for {} was not approved.{} Your schedule is "
        "unchanged.".format(span, tail),
        ref_type=RefType.LEAVE,
        ref_id=request_id,
    )


# ── Care record ────────────────────────────────────────────────────────────


async def notify_report_uploaded(
    db: Prisma,
    report_id: str,
    *,
    patient_user_id: str,
    title: str = "",
    therapist_name: str = "",
) -> None:
    """A therapist filed a report or exercise plan for the patient."""
    who = therapist_name or "Your therapist"
    what = (title or "").strip()
    detail = ' "{}" is ready to read.'.format(what) if what else " is ready to read."
    await notify_once(
        db,
        patient_user_id,
        type=NotificationType.REPORT_UPLOADED,
        title="New report from your therapist",
        body="{} shared a report with you.{}".format(who, detail),
        ref_type=RefType.REPORT,
        ref_id=report_id,
    )


# ── Rewards ────────────────────────────────────────────────────────────────


async def notify_referral_joined(
    db: Prisma, *, referrer_user_id: str, joiner_name: str = "", joiner_user_id: str = ""
) -> None:
    """Someone signed up with this user's referral code.

    Keyed on the joiner, so it is written once per person invited -- the payout
    that follows their first completed session is a separate event.
    """
    name = _first_name(joiner_name) or "Someone"
    await notify_once(
        db,
        referrer_user_id,
        type=NotificationType.REFERRAL_JOINED,
        title="{} joined with your code".format(name),
        body="{} signed up using your referral code. You earn points once they "
        "complete their first session.".format(name),
        ref_type=RefType.REFERRAL,
        ref_id=joiner_user_id or None,
    )


async def notify_referral_rewarded(
    db: Prisma, user_id: str, points: int, *, transaction_id: str | None = None
) -> None:
    """Referral points landed in the ledger."""
    await notify_once(
        db,
        user_id,
        type=NotificationType.REFERRAL_REWARDED,
        title="You earned {} points".format(points),
        body="Your referral completed their first session. Points become "
        "available after a short hold.",
        ref_type=RefType.REFERRAL,
        ref_id=transaction_id,
    )


async def notify_points_matured(db: Prisma, user_id: str, points: int) -> None:
    """Held points finished their hold and can now be spent.

    Naturally once-per-row: maturation flips PENDING to AVAILABLE, so the same
    points can never mature twice.
    """
    if points <= 0:
        return
    await safe_notify(
        db,
        user_id,
        type=NotificationType.POINTS_MATURED,
        title="{} points are ready to use".format(points),
        body="Your held points have cleared. Apply them to your next booking "
        "to lower the fee.",
        ref_type=RefType.POINTS,
    )
