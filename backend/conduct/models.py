from django.conf import settings
from django.db import models
from parties.models import Party

REVIEW_UNIQUE_CONSTRAINT = "unique_party_review"
NO_SHOW_UNIQUE_CONSTRAINT = "unique_no_show_report"
CREDIT_EVENT_UNIQUE_CONSTRAINT = "unique_conduct_credit_event"


class PartyReview(models.Model):
    # PROTECT, not CASCADE: UserProfile.rating_sum/rating_count are caches of these rows.
    # Cascading a Party delete would drop the reviews without reducing the caches, and
    # the read API reads the caches directly.
    party = models.ForeignKey(
        Party,
        on_delete=models.PROTECT,
        related_name="reviews",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviews_written",
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviews_received",
    )
    rating = models.SmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["party", "reviewer", "reviewee"],
                name=REVIEW_UNIQUE_CONSTRAINT,
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="party_review_rating_1_to_5",
            ),
            models.CheckConstraint(
                condition=~models.Q(reviewer=models.F("reviewee")),
                name="party_review_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["reviewee", "created_at"], name="review_reviewee_created_idx"),
        ]


class NoShowReport(models.Model):
    party = models.ForeignKey(
        Party,
        on_delete=models.CASCADE,
        related_name="no_show_reports",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="no_show_reports_filed",
    )
    reported = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="no_show_reports_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["party", "reporter", "reported"],
                name=NO_SHOW_UNIQUE_CONSTRAINT,
            ),
            models.CheckConstraint(
                condition=~models.Q(reporter=models.F("reported")),
                name="no_show_report_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["party", "reported"], name="no_show_party_reported_idx"),
        ]


class ConductCreditEvent(models.Model):
    """Append-only credit ledger; correct a balance with a new event, never an update."""

    class Kind(models.TextChoices):
        NO_SHOW_DEDUCTION = "NoShowDeduction", "หักเครดิตจากการไม่มาร่วมกิจกรรม"
        ADMIN_ADJUSTMENT = "AdminAdjustment", "ผู้ดูแลปรับเครดิต"
        APPEAL_REVERSAL = "AppealReversal", "คืนเครดิตจากการอุทธรณ์"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="credit_events",
    )
    party = models.ForeignKey(
        Party,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_events",
    )
    kind = models.CharField(max_length=15, choices=Kind.choices)
    delta = models.IntegerField()
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_events_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Rows with party NULL (admin adjustments) are not limited by this constraint.
            models.UniqueConstraint(
                fields=["party", "user", "kind"],
                name=CREDIT_EVENT_UNIQUE_CONSTRAINT,
            ),
            models.CheckConstraint(
                condition=~models.Q(delta=0),
                name="credit_event_delta_not_zero",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "created_at"], name="credit_event_user_created_idx"),
        ]
