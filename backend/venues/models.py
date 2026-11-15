from django.db import models


class Sport(models.Model):
    name = models.CharField(max_length=80, unique=True)


class Venue(models.Model):
    class Type(models.TextChoices):
        INDOOR = "Indoor", "Indoor"
        OUTDOOR = "Outdoor", "Outdoor"

    name = models.CharField(max_length=150)
    location_text = models.CharField(max_length=255)
    venue_type = models.CharField(
        max_length=7,
        choices=Type.choices,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)


class VenueSport(models.Model):
    venue = models.ForeignKey(
        Venue,
        on_delete=models.CASCADE,
        related_name="venue_sports",
    )
    sport = models.ForeignKey(
        Sport,
        on_delete=models.PROTECT,
        related_name="venue_sports",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["venue", "sport"],
                name="unique_venue_sport",
            ),
        ]


class VenueOpeningHour(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "จันทร์"
        TUESDAY = 1, "อังคาร"
        WEDNESDAY = 2, "พุธ"
        THURSDAY = 3, "พฤหัสบดี"
        FRIDAY = 4, "ศุกร์"
        SATURDAY = 5, "เสาร์"
        SUNDAY = 6, "อาทิตย์"

    venue = models.ForeignKey(
        Venue,
        on_delete=models.CASCADE,
        related_name="opening_hours",
    )
    weekday = models.SmallIntegerField(choices=Weekday.choices)
    opens_at = models.TimeField()
    closes_at = models.TimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weekday__gte=0, weekday__lte=6),
                name="venue_hour_valid_weekday",
            ),
            models.CheckConstraint(
                condition=models.Q(closes_at__gt=models.F("opens_at")),
                name="venue_hour_close_after_open",
            ),
            models.UniqueConstraint(
                fields=["venue", "weekday", "opens_at"],
                name="unique_venue_hour_start",
            ),
        ]
