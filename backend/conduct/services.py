"""Party review and No-show rules. Writers must lock Party before these tables and caches."""

from datetime import timedelta

from accounts.models import UserProfile
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone
from parties.models import Party
from parties.services import PartyError, get_party_state

from .models import (
    CREDIT_EVENT_UNIQUE_CONSTRAINT,
    NO_SHOW_UNIQUE_CONSTRAINT,
    REVIEW_UNIQUE_CONSTRAINT,
    ConductCreditEvent,
    NoShowReport,
    PartyReview,
)
from .policy import CREDIT_BASE, NO_SHOW_DEDUCTION, REPORT_WINDOW_DAYS, required_reporters


def stayed_until_end(party):
    """Memberships of members who stayed until the activity ended (left_at >= ends_at)."""
    return party.memberships.filter(Q(left_at__isnull=True) | Q(left_at__gte=party.ends_at))


def is_participant(party, user_id):
    """Host, or a member who stayed until the activity ended."""
    if user_id == party.host_id:
        return True
    return stayed_until_end(party).filter(user_id=user_id).exists()


def invalid_reviewee():
    # One message for every cause so the response never reveals whether a user exists.
    return PartyError(
        "INVALID_INPUT",
        "ข้อมูลรีวิวไม่ถูกต้อง",
        fields={"reviewee_id": "ไม่สามารถรีวิวผู้ใช้นี้ได้"},
    )


@transaction.atomic
def submit_review(*, party_id, reviewer, reviewee_id, rating, comment):
    """Store one review and its rating cache change together, or neither.

    The caller supplies the trusted reviewer and input validated by the API.
    """
    try:
        party = Party.objects.select_for_update().get(pk=party_id)
    except Party.DoesNotExist:
        raise PartyError("NOT_FOUND", "ไม่พบกิจกรรมที่ต้องการ", 404) from None

    # Evaluate time after acquiring the lock: a waiting request may cross ends_at.
    if get_party_state(party, timezone.now()) != "Completed":
        raise PartyError("PARTY_NOT_COMPLETED", "รีวิวได้เฉพาะกิจกรรมที่จบแล้ว", 409)
    if not is_participant(party, reviewer.pk):
        raise PartyError("FORBIDDEN", "เฉพาะผู้เข้าร่วมกิจกรรมเท่านั้นที่รีวิวได้", 403)
    if reviewee_id == reviewer.pk:
        raise PartyError(
            "INVALID_INPUT",
            "ข้อมูลรีวิวไม่ถูกต้อง",
            fields={"reviewee_id": "ไม่สามารถรีวิวตัวเองได้"},
        )
    if not is_participant(party, reviewee_id):
        raise invalid_reviewee()

    # The unique constraint is the duplicate check; other integrity errors are bugs.
    try:
        with transaction.atomic():
            review = PartyReview.objects.create(
                party=party,
                reviewer=reviewer,
                reviewee_id=reviewee_id,
                rating=rating,
                comment=comment,
            )
    except IntegrityError as error:
        if REVIEW_UNIQUE_CONSTRAINT not in str(error):
            raise
        raise PartyError("REVIEW_EXISTS", "คุณรีวิวผู้ใช้นี้ในกิจกรรมนี้แล้ว", 409) from None

    updated = UserProfile.objects.filter(user_id=reviewee_id).update(
        rating_sum=F("rating_sum") + rating,
        rating_count=F("rating_count") + 1,
    )
    # Legacy accounts have no cache to update; raising also rolls back the insert,
    # so a review can never exist that the rating cache does not count.
    if not updated:
        raise invalid_reviewee()
    return review


def average_rating(profile):
    """Read the stars from the rating cache; no reviews means null, not zero."""
    if not profile.rating_count:
        return None
    return round(profile.rating_sum / profile.rating_count, 2)


def list_reviews(user_id, page, page_size):
    """Return the reviewee's profile, one page of reviews (newest first) and the total."""
    profile = UserProfile.objects.filter(user_id=user_id).first()
    if profile is None:
        raise PartyError("NOT_FOUND", "ไม่พบผู้ใช้ที่ต้องการ", 404)
    reviews = PartyReview.objects.filter(reviewee_id=user_id)
    total = reviews.count()
    offset = (page - 1) * page_size
    # A page past the end skips the query, so a huge page cannot overflow OFFSET.
    rows = (
        []
        if offset >= total
        else list(
            reviews.select_related("reviewer__profile").order_by("-created_at", "-pk")[
                offset : offset + page_size
            ]
        )
    )
    return profile, rows, total


def invalid_reported():
    # One message for every cause so the response never reveals whether a user exists.
    return PartyError(
        "INVALID_INPUT",
        "ข้อมูลรายงานไม่ถูกต้อง",
        fields={"reported_id": "ไม่สามารถรายงานผู้ใช้นี้ได้"},
    )


def eligible_reporter_count(party, reported_id):
    """Participants of the party excluding the reported user."""
    participants = set(stayed_until_end(party).values_list("user_id", flat=True))
    participants.add(party.host_id)
    participants.discard(reported_id)
    return len(participants)


def apply_credit_event(user_id, party, kind, delta, note):
    """Append one ledger event and change credit_score with it; None if already applied.

    The caller must hold the transaction. The profile row lock serializes balance changes.
    """
    profile = UserProfile.objects.select_for_update().filter(user_id=user_id).first()
    if profile is None:
        raise invalid_reported()
    try:
        with transaction.atomic():
            event = ConductCreditEvent.objects.create(
                user_id=user_id, party=party, kind=kind, delta=delta, note=note
            )
    except IntegrityError as error:
        if CREDIT_EVENT_UNIQUE_CONSTRAINT not in str(error):
            raise
        return None
    base = CREDIT_BASE if profile.credit_score is None else profile.credit_score
    profile.credit_score = base + delta
    profile.save(update_fields=["credit_score"])
    return event


@transaction.atomic
def submit_no_show_report(*, party_id, reporter, reported_id):
    """Store one report and, once enough reporters agree, deduct credit once.

    The caller supplies the trusted reporter and input validated by the API.
    Returns only the report: a reporter must not learn whether it triggered a deduction.
    """
    try:
        party = Party.objects.select_for_update().get(pk=party_id)
    except Party.DoesNotExist:
        raise PartyError("NOT_FOUND", "ไม่พบกิจกรรมที่ต้องการ", 404) from None

    # Evaluate time after acquiring the lock: a waiting request may cross either boundary.
    now = timezone.now()
    if get_party_state(party, now) != "Completed":
        raise PartyError("PARTY_NOT_COMPLETED", "รายงานได้เฉพาะกิจกรรมที่จบแล้ว", 409)
    if now > party.ends_at + timedelta(days=REPORT_WINDOW_DAYS):
        raise PartyError("REPORT_WINDOW_CLOSED", "หมดเวลารายงานกิจกรรมนี้แล้ว", 409)
    if not is_participant(party, reporter.pk):
        raise PartyError("FORBIDDEN", "เฉพาะผู้เข้าร่วมกิจกรรมเท่านั้นที่รายงานได้", 403)
    if reported_id == reporter.pk:
        raise PartyError(
            "INVALID_INPUT",
            "ข้อมูลรายงานไม่ถูกต้อง",
            fields={"reported_id": "ไม่สามารถรายงานตัวเองได้"},
        )
    # Check the profile before any report, so it cannot pass only below the threshold.
    if (
        not is_participant(party, reported_id)
        or not UserProfile.objects.filter(user_id=reported_id).exists()
    ):
        raise invalid_reported()

    # The unique constraint is the duplicate check; other integrity errors are bugs.
    try:
        with transaction.atomic():
            report = NoShowReport.objects.create(
                party=party, reporter=reporter, reported_id=reported_id
            )
    except IntegrityError as error:
        if NO_SHOW_UNIQUE_CONSTRAINT not in str(error):
            raise
        raise PartyError("REPORT_EXISTS", "คุณรายงานผู้ใช้นี้ในกิจกรรมนี้แล้ว", 409) from None

    kind = ConductCreditEvent.Kind.NO_SHOW_DEDUCTION
    # unique(party, reporter, reported) makes each row one distinct reporter.
    reporters = NoShowReport.objects.filter(party=party, reported_id=reported_id).count()
    if (
        reporters >= required_reporters(eligible_reporter_count(party, reported_id))
        and not ConductCreditEvent.objects.filter(
            party=party, user_id=reported_id, kind=kind
        ).exists()
    ):
        apply_credit_event(
            reported_id, party, kind, NO_SHOW_DEDUCTION, "หักเครดิตตามรายงานไม่มาร่วมกิจกรรม"
        )
    return report
