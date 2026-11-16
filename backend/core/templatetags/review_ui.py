from conduct.models import PartyReview
from conduct.services import stayed_until_end
from conduct.views import reviewer_display_name
from django import template
from django.contrib.auth import get_user_model
from django.db.models import F, Q
from django.utils import timezone
from parties.models import Party

register = template.Library()


@register.inclusion_tag("partials/review_history_content.html")
def review_history(user):
    if not user.is_authenticated:
        return {"history": []}
    parties = list(
        Party.objects.filter(cancelled_at__isnull=True, ends_at__lte=timezone.now())
        .filter(
            Q(host=user)
            | Q(memberships__user=user, memberships__left_at__isnull=True)
            | Q(memberships__user=user, memberships__left_at__gte=F("ends_at"))
        )
        .select_related("sport", "venue")
        .distinct()
        .order_by("-ends_at", "-pk")
    )
    written = set(
        PartyReview.objects.filter(reviewer=user, party__in=parties).values_list(
            "party_id", "reviewee_id"
        )
    )
    for party in parties:
        member_ids = stayed_until_end(party).values_list("user_id", flat=True)
        targets = (
            get_user_model()
            .objects.filter(Q(pk=party.host_id) | Q(pk__in=member_ids))
            .exclude(pk=user.pk)
            .select_related("profile")
            .order_by("pk")
        )
        party.review_targets = [
            {
                "id": target.pk,
                "name": reviewer_display_name(target),
                "reviewed": (party.pk, target.pk) in written,
            }
            for target in targets
            if getattr(target, "profile", None) is not None
        ]
        party.can_review = any(not t["reviewed"] for t in party.review_targets)
    return {"history": parties}
