from django.conf import settings
from django.db import models
from parties.models import Party

REVIEW_UNIQUE_CONSTRAINT = "unique_party_review"


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
