from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Local application account; this model alone does not verify student status."""


class UniversityIdentity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="university_identities",
    )
    provider_key = models.CharField(max_length=150)
    subject = models.CharField(max_length=255)
    student_verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    eligibility_checked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider_key", "subject"],
                name="unique_university_identity",
            ),
        ]


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=100)
    credit_score = models.IntegerField(
        null=True,
        blank=True,
    )
    # Aggregate of conduct.PartyReview, written only by conduct.services.submit_review.
    rating_sum = models.IntegerField(default=0)
    rating_count = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(display_name=""),
                name="user_profile_name_not_empty",
            ),
            models.CheckConstraint(
                condition=~models.Q(display_name__regex=r"^\s*$"),
                name="user_profile_name_not_blank",
            ),
            models.CheckConstraint(
                condition=models.Q(rating_sum__gte=0),
                name="user_profile_rating_sum_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(rating_count__gte=0),
                name="user_profile_rating_count_gte_0",
            ),
        ]


class UserSportInterest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sport_interests",
    )
    sport = models.ForeignKey(
        "venues.Sport",
        on_delete=models.CASCADE,
        related_name="interested_users",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "sport"],
                name="unique_user_sport_interest",
            ),
        ]
