"""Party review rules. Writers must lock Party before reviews and the rating cache."""

from accounts.models import UserProfile
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone
from parties.models import Party
from parties.services import PartyError, get_party_state

from .models import REVIEW_UNIQUE_CONSTRAINT, PartyReview


def is_participant(party, user_id):
    """Host, or a member who stayed until the activity ended (left_at >= ends_at)."""
    if user_id == party.host_id:
        return True
    return party.memberships.filter(
        Q(left_at__isnull=True) | Q(left_at__gte=party.ends_at), user_id=user_id
    ).exists()


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
