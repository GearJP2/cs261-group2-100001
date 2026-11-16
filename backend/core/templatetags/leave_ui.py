from django import template
from django.db.models import Count, Q
from django.utils import timezone
from parties.models import JoinRequest, Party
from parties.services import get_party_state

register = template.Library()


@register.inclusion_tag("partials/joined_party_content.html")
def joined_parties(user):
    if not user.is_authenticated:
        return {"joined": []}
    active = Party.objects.filter(memberships__user=user, memberships__left_at__isnull=True)
    pending = JoinRequest.objects.filter(user=user, status="Pending").values("party_id")
    parties = list(
        Party.objects.filter(Q(pk__in=active.values("pk")) | Q(pk__in=pending))
        .select_related("sport", "venue")
        .annotate(ui_count=Count("memberships", filter=Q(memberships__left_at__isnull=True)))
        .order_by("starts_at", "pk")
    )
    active_ids = set(active.values_list("pk", flat=True))
    now = timezone.now()
    for party in parties:
        party.ui_state = get_party_state(party, now, member_count=party.ui_count)
        party.ui_active = party.pk in active_ids
        if party.host_id == user.pk:
            party.ui_leave_reason = "ผู้จัดกิจกรรมต้องใช้การยกเลิกกิจกรรมแทน"
        elif not party.ui_active:
            party.ui_leave_reason = "คำขอยังรออนุมัติ คุณยังไม่เป็นสมาชิก"
        elif party.cancelled_at is not None:
            party.ui_leave_reason = "กิจกรรมถูกยกเลิกแล้ว"
        elif now >= party.starts_at:
            party.ui_leave_reason = "กิจกรรมเริ่มหรือจบแล้ว ไม่สามารถถอนตัวได้"
        else:
            party.ui_leave_reason = ""
    return {"joined": parties, "viewer_id": user.pk}
