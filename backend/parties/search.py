"""US2 query validation and filtered querysets for the Party list API."""

import re
from datetime import timezone as datetime_timezone

from django.db.models import Case, CharField, Count, F, Q, Value, When
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Party
from .services import PartyError

SEARCH_FIELDS = {
    "q",
    "sport_id",
    "venue_id",
    "venue_type",
    "starts_from",
    "starts_to",
    "state",
    "page",
    "page_size",
}
SEARCH_STATES = {"Open", "Full", "InProgress", "Completed", "Cancelled", "all"}


def parse_search_query(query):
    """Validate a QueryDict, retaining duplicates for validation before conversion.

    Returns trimmed text, integers, enum strings and aware UTC datetimes.
    No database access or actor selection is performed here.
    """
    fields = {}
    values = {"q": "", "state": "Open", "page": 1, "page_size": 20}
    for key, entries in query.lists():
        if key not in SEARCH_FIELDS:
            fields[key] = "ไม่รองรับตัวกรองนี้"
            continue
        if len(entries) != 1:
            fields[key] = "ระบุตัวกรองได้เพียงครั้งเดียว"
            continue
        value = entries[0]
        if key == "q":
            value = value.strip()
            if "\x00" in value:
                fields[key] = "ข้อความค้นหาต้องไม่มีอักขระ NUL"
            elif len(value) > 100:
                fields[key] = "ข้อความค้นหายาวได้ไม่เกิน 100 ตัวอักษร"
            else:
                values[key] = value
        elif key in {"sport_id", "venue_id", "page", "page_size"}:
            if not re.fullmatch(r"[0-9]+", value):
                fields[key] = "ต้องเป็นจำนวนเต็มบวก"
                continue
            try:
                number = int(value)
            except ValueError:
                fields[key] = "จำนวนเต็มอยู่นอกช่วงที่รองรับ"
                continue
            if number < 1 or (key == "page_size" and number > 100):
                fields[key] = "ต้องเป็นจำนวนเต็ม 1–100" if key == "page_size" else "ต้องเป็นจำนวนเต็มบวก"
            else:
                values[key] = number
        elif key in {"state", "venue_type"}:
            allowed = SEARCH_STATES if key == "state" else {"Indoor", "Outdoor"}
            if value not in allowed:
                fields[key] = "ค่าตัวกรองไม่ถูกต้อง"
            else:
                values[key] = value
        else:
            try:
                parsed = parse_datetime(value) if "T" in value else None
                if parsed is None or timezone.is_naive(parsed):
                    raise ValueError
                values[key] = parsed.astimezone(datetime_timezone.utc)
            except (ValueError, OverflowError):
                fields[key] = "กรุณาระบุ ISO 8601 datetime พร้อม timezone ที่อยู่ในช่วงที่รองรับ"
    if "starts_from" in values and "starts_to" in values:
        if values["starts_from"] >= values["starts_to"]:
            fields["starts_to"] = "ต้องอยู่หลัง starts_from"
    if fields:
        raise PartyError("INVALID_INPUT", "ตัวกรองค้นหาไม่ถูกต้อง", 400, fields)
    return values


def search_parties(filters, *, now):
    """Build an ordered queryset from validated filters at one aware instant.

    State precedence mirrors get_party_state; all counts include only active
    membership rows. No joins to requests or supported sports multiply counts.
    The caller supplies the same now when serializing the results.
    """
    parties = (
        Party.objects.select_related("host__profile")
        .annotate(
            active_member_count=Count("memberships", filter=Q(memberships__left_at__isnull=True)),
        )
        .annotate(
            search_state=Case(
                When(cancelled_at__isnull=False, then=Value("Cancelled")),
                When(ends_at__lte=now, then=Value("Completed")),
                When(starts_at__lte=now, then=Value("InProgress")),
                When(active_member_count__gte=F("capacity"), then=Value("Full")),
                default=Value("Open"),
                output_field=CharField(),
            )
        )
    )
    for key, lookup in {
        "sport_id": "sport_id",
        "venue_id": "venue_id",
        "venue_type": "venue__venue_type",
        "starts_from": "starts_at__gte",
        "starts_to": "starts_at__lt",
    }.items():
        if key in filters:
            parties = parties.filter(**{lookup: filters[key]})
    if filters["q"]:
        parties = parties.filter(title__icontains=filters["q"])
    if filters["state"] != "all":
        parties = parties.filter(search_state=filters["state"])
    return parties.order_by("starts_at", "pk")
