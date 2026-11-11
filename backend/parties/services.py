"""Shared Party rules. Writers must lock Party before requests/memberships."""

from datetime import datetime

from django.db import transaction
from django.utils import timezone
from venues.services import ScheduleValidationError, validate_party_schedule

from .models import JoinRequest, Party, PartyMembership

# PostgreSQL IntegerField upper bound; no lower business limit is defined yet.
MAX_PARTY_CAPACITY = 2_147_483_647


class PartyError(Exception):
    def __init__(self, code, message, status=400, fields=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.fields = fields


class JoinRequestError(Exception):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def active_memberships(party):
    """Read actual active rows, retaining users without a profile and all history."""
    return (
        party.memberships.filter(left_at__isnull=True)
        .select_related("user__profile")
        .order_by("joined_at", "pk")
    )


def count_active_members(party):
    return active_memberships(party).count()


def get_party_state(party, now=None, *, member_count=None):
    """Use one timestamp and, optionally, the count already read by the caller."""
    if now is None:
        now = timezone.now()
    if party.cancelled_at is not None:
        return "Cancelled"
    if now >= party.ends_at:
        return "Completed"
    if now >= party.starts_at:
        return "InProgress"
    if member_count is None:
        member_count = count_active_members(party)
    if member_count >= party.capacity:
        return "Full"
    return "Open"


def validate_party_data(
    *, title, description, sport_id, venue_id, starts_at, ends_at, capacity, now
):
    """Validate the complete candidate data shared by creation and editing."""
    fields = {}
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 150:
        fields["title"] = "กรุณาระบุชื่อกิจกรรมไม่เกิน 150 ตัวอักษร"
    if not isinstance(description, str) or len(description) > 2000:
        fields["description"] = "รายละเอียดต้องเป็นข้อความไม่เกิน 2,000 ตัวอักษร"
    for field, value in (("title", title), ("description", description)):
        if isinstance(value, str) and "\x00" in value:
            fields[field] = "ข้อความต้องไม่มีอักขระ NUL"
    if type(capacity) is not int or not 1 <= capacity <= MAX_PARTY_CAPACITY:
        fields["capacity"] = f"จำนวนผู้เข้าร่วมต้องเป็นจำนวนเต็มตั้งแต่ 1 ถึง {MAX_PARTY_CAPACITY:,}"
    for field, value in (("starts_at", starts_at), ("ends_at", ends_at)):
        if not isinstance(value, datetime) or timezone.is_naive(value):
            fields[field] = "กรุณาระบุวันเวลาที่มี timezone"
    if fields:
        raise PartyError("INVALID_INPUT", "ข้อมูลกิจกรรมไม่ถูกต้อง", fields=fields)

    if starts_at <= now:
        fields["starts_at"] = "เวลาเริ่มกิจกรรมต้องอยู่ในอนาคต"
    if ends_at <= starts_at:
        fields["ends_at"] = "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม"
    if fields:
        raise PartyError("INVALID_TIME_RANGE", "ช่วงเวลาไม่ถูกต้อง", fields=fields)

    try:
        validate_party_schedule(sport_id, venue_id, starts_at, ends_at)
    except ScheduleValidationError as error:
        raise PartyError(error.code, error.message, error.status, error.fields) from error


@transaction.atomic
def create_party(
    *,
    user,
    title,
    description,
    sport_id,
    venue_id,
    starts_at,
    ends_at,
    capacity,
):
    """Validate basic fields and persist Party and Host membership together.

    The caller must supply the authenticated user and parsed datetimes.
    Validate the full schedule with the shared US9 rules before writing.
    """
    validate_party_data(
        title=title,
        description=description,
        sport_id=sport_id,
        venue_id=venue_id,
        starts_at=starts_at,
        ends_at=ends_at,
        capacity=capacity,
        now=timezone.now(),
    )

    party = Party.objects.create(
        host=user,
        title=title.strip(),
        description=description,
        sport_id=sport_id,
        venue_id=venue_id,
        starts_at=starts_at,
        ends_at=ends_at,
        capacity=capacity,
    )
    PartyMembership.objects.create(party=party, user=user)
    return party


PARTY_EDIT_FIELDS = frozenset(
    {
        "title",
        "description",
        "sport_id",
        "venue_id",
        "starts_at",
        "ends_at",
        "capacity",
    }
)


@transaction.atomic
def edit_party(*, party_id, user, changes):
    """Merge a partial update under the Party lock, then validate before writing.

    The caller supplies a trusted user and parsed datetimes. Pending requests
    and memberships are preserved when the schedule changes.
    """
    try:
        party = Party.objects.select_for_update().get(pk=party_id)
    except Party.DoesNotExist:
        raise PartyError("NOT_FOUND", "ไม่พบกิจกรรมที่ต้องการ", 404) from None
    if party.host_id != user.pk:
        raise PartyError("FORBIDDEN", "เฉพาะผู้จัดกิจกรรมเท่านั้นที่แก้ไขได้", 403)
    now = timezone.now()
    if party.cancelled_at is not None:
        raise PartyError("PARTY_CANCELLED", "กิจกรรมนี้ถูกยกเลิกแล้ว", 409)
    if now >= party.starts_at:
        raise PartyError("PARTY_STARTED", "กิจกรรมนี้เริ่มแล้ว", 409)
    if not isinstance(changes, dict):
        raise PartyError("INVALID_INPUT", "ข้อมูลต้องเป็น object")
    unknown = changes.keys() - PARTY_EDIT_FIELDS
    if unknown:
        raise PartyError(
            "INVALID_INPUT",
            "มีฟิลด์ที่ไม่อนุญาต",
            fields={key: "ไม่รองรับฟิลด์นี้" for key in unknown},
        )
    candidate = {key: changes.get(key, getattr(party, key)) for key in PARTY_EDIT_FIELDS}
    validate_party_data(**candidate, now=now)
    if candidate["capacity"] < count_active_members(party):
        raise PartyError(
            "CAPACITY_TOO_SMALL",
            "ความจุต้องไม่ต่ำกว่าจำนวนสมาชิกปัจจุบัน",
            409,
            {"capacity": "กรุณาระบุความจุไม่น้อยกว่าจำนวนสมาชิกปัจจุบัน"},
        )
    if not changes:
        return party
    candidate["title"] = candidate["title"].strip()
    for key, value in candidate.items():
        setattr(party, key, value)
    party.save(update_fields=[*sorted(PARTY_EDIT_FIELDS), "updated_at"])
    return party


@transaction.atomic
def cancel_party(*, party_id, user):
    """Cancel before start, preserving history and the first cancellation time.

    The caller supplies the trusted user after authentication/eligibility checks.
    Lock Party first, following the same order as join and other writers.
    """
    try:
        party = Party.objects.select_for_update().get(pk=party_id)
    except Party.DoesNotExist:
        raise PartyError("NOT_FOUND", "ไม่พบกิจกรรมที่ต้องการ", 404) from None

    if party.host_id != user.pk:
        raise PartyError("FORBIDDEN", "เฉพาะผู้จัดกิจกรรมเท่านั้นที่ยกเลิกได้", 403)
    if party.cancelled_at is not None:
        return party

    # A waiting transaction may acquire the lock after the activity starts.
    now = timezone.now()
    if now >= party.starts_at:
        raise PartyError("PARTY_STARTED", "กิจกรรมนี้เริ่มแล้ว", 409)

    party.cancelled_at = now
    party.save(update_fields=["cancelled_at", "updated_at"])
    return party


@transaction.atomic
def submit_join_request(*, party_id, user):
    """Create/reopen a Pending request without changing membership or capacity.

    The Party lock serializes competing requests and is also the lock that
    approval, withdrawal and cancellation services must acquire first.
    The caller must apply the shared authentication/eligibility guard and pass
    its trusted user, never a user selected from request data.
    """
    try:
        party = Party.objects.select_for_update().get(pk=party_id)
    except Party.DoesNotExist:
        raise JoinRequestError("NOT_FOUND", "ไม่พบกิจกรรมที่ต้องการ", 404) from None

    # Evaluate time after acquiring the lock: a waiting request may cross starts_at.
    now = timezone.now()
    state = get_party_state(party, now)
    if state == "Cancelled":
        raise JoinRequestError("PARTY_CANCELLED", "กิจกรรมนี้ถูกยกเลิกแล้ว")
    if state in {"InProgress", "Completed"}:
        raise JoinRequestError("PARTY_STARTED", "กิจกรรมนี้เริ่มแล้ว")
    if state == "Full":
        raise JoinRequestError("PARTY_FULL", "กิจกรรมนี้เต็มแล้ว")

    membership = party.memberships.filter(user=user).first()
    if party.host_id == user.pk or (membership is not None and membership.left_at is None):
        raise JoinRequestError("ALREADY_MEMBER", "คุณเป็นสมาชิกของกิจกรรมนี้แล้ว")

    # The existing unique(party, user) constraint remains the final DB safeguard.
    join_request, created = JoinRequest.objects.select_for_update().get_or_create(
        party=party, user=user
    )
    if created:
        return join_request
    if join_request.status == JoinRequest.Status.PENDING:
        raise JoinRequestError("REQUEST_EXISTS", "คุณส่งคำขอเข้าร่วมกิจกรรมนี้แล้ว")
    if join_request.status == JoinRequest.Status.APPROVED and (
        membership is None or membership.left_at is None
    ):
        raise JoinRequestError("REQUEST_DECIDED", "คำขอนี้ได้รับการตัดสินแล้ว")

    # Schema contract 4.1.1: reuse the latest request after rejection/withdrawal.
    join_request.status = JoinRequest.Status.PENDING
    join_request.created_at = now
    join_request.decided_at = None
    join_request.decided_by = None
    join_request.save(update_fields=["status", "created_at", "decided_at", "decided_by"])
    return join_request


@transaction.atomic
def decide_join_request(*, party_id, request_id, user, approved):
    """Decide atomically, locking Party -> JoinRequest -> existing Membership.

    Party is the mutex even when the applicant has no Membership row to lock.
    All capacity-changing writers must take that same Party lock first; a unique
    constraint alone cannot prevent two different applicants taking the last slot.
    Let DB errors escape this atomic boundary so both domain writes roll back.
    """
    try:
        party = Party.objects.select_for_update().get(pk=party_id)
    except Party.DoesNotExist:
        raise PartyError("NOT_FOUND", "ไม่พบกิจกรรมที่ต้องการ", 404) from None
    if party.host_id != user.pk:
        raise PartyError("FORBIDDEN", "เฉพาะผู้จัดกิจกรรมเท่านั้นที่จัดการคำขอได้", 403)
    try:
        join_request = JoinRequest.objects.select_for_update().get(pk=request_id, party=party)
    except JoinRequest.DoesNotExist:
        raise PartyError("NOT_FOUND", "ไม่พบคำขอเข้าร่วม", 404) from None
    if join_request.status != JoinRequest.Status.PENDING:
        raise PartyError("REQUEST_DECIDED", "คำขอนี้ได้รับการตัดสินแล้ว", 409)

    state = get_party_state(party, timezone.now())
    if state == "Cancelled":
        raise PartyError("PARTY_CANCELLED", "กิจกรรมนี้ถูกยกเลิกแล้ว", 409)
    if state in {"InProgress", "Completed"}:
        raise PartyError("PARTY_STARTED", "กิจกรรมนี้เริ่มแล้ว", 409)
    if approved:
        if state == "Full":
            raise PartyError("PARTY_FULL", "กิจกรรมนี้เต็มแล้ว", 409)
        membership = (
            PartyMembership.objects.select_for_update()
            .filter(party=party, user_id=join_request.user_id)
            .first()
        )
        # Pending rows from legacy/imported data must not approve an existing member.
        if join_request.user_id == party.host_id or (
            membership is not None and membership.left_at is None
        ):
            raise PartyError("ALREADY_MEMBER", "ผู้ขอเป็นสมาชิกของกิจกรรมนี้แล้ว", 409)
        if membership is None:
            PartyMembership.objects.create(party=party, user_id=join_request.user_id)
        else:
            membership.left_at = None
            membership.save(update_fields=["left_at"])

    join_request.status = JoinRequest.Status.APPROVED if approved else JoinRequest.Status.REJECTED
    join_request.decided_at = timezone.now()
    join_request.decided_by = user
    join_request.save(update_fields=["status", "decided_at", "decided_by"])
    return join_request
