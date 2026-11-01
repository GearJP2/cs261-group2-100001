import json

from accounts.decorators import require_university_user
from core.api import json_error, require_authenticated_api
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import JoinRequest, Party
from .services import (
    PARTY_EDIT_FIELDS,
    JoinRequestError,
    PartyError,
    cancel_party,
    count_active_members,
    create_party,
    decide_join_request,
    edit_party,
    get_party_state,
    submit_join_request,
)


def party_data(party, user):
    profile = getattr(party.host, "profile", None)
    member_count = (
        party.active_member_count
        if hasattr(party, "active_member_count")
        else count_active_members(party)
    )
    return {
        "id": party.pk,
        "title": party.title,
        "description": party.description,
        "host": {
            "id": party.host_id,
            # Legacy/local accounts may not have a profile. Never expose
            # their login identifier as a replacement display name.
            "display_name": profile.display_name if profile else "ผู้จัดกิจกรรม",
        },
        "sport_id": party.sport_id,
        "venue_id": party.venue_id,
        "starts_at": timezone.localtime(party.starts_at).isoformat(),
        "ends_at": timezone.localtime(party.ends_at).isoformat(),
        "capacity": party.capacity,
        "member_count": member_count,
        "remaining_slots": party.capacity - member_count,
        "state": get_party_state(party, member_count=member_count),
        "is_host": user.pk == party.host_id,
        "is_member": party.memberships.filter(user=user, left_at__isnull=True).exists(),
    }


@never_cache
@require_authenticated_api
def party_detail(request, party_id):
    if request.method == "PATCH":
        return edit_party_api(request, party_id)
    if request.method != "GET":
        response = json_error("METHOD_NOT_ALLOWED", "รองรับเฉพาะ GET และ PATCH", 405)
        response["Allow"] = "GET, PATCH"
        return response

    try:
        party = Party.objects.select_related("host__profile").get(pk=party_id)
    except Party.DoesNotExist:
        return json_error("NOT_FOUND", "ไม่พบกิจกรรมที่ต้องการ", 404)

    profile = getattr(party.host, "profile", None)
    member_count = count_active_members(party)
    return JsonResponse(
        {
            "data": {
                "id": party.pk,
                "title": party.title,
                "description": party.description,
                "host": {
                    "id": party.host_id,
                    # Legacy/local accounts may not have a profile. Never expose
                    # their login identifier as a replacement display name.
                    "display_name": profile.display_name if profile else "ผู้จัดกิจกรรม",
                },
                "sport_id": party.sport_id,
                "venue_id": party.venue_id,
                "starts_at": timezone.localtime(party.starts_at).isoformat(),
                "ends_at": timezone.localtime(party.ends_at).isoformat(),
                "capacity": party.capacity,
                "member_count": member_count,
                "remaining_slots": party.capacity - member_count,
                "state": get_party_state(party, member_count=member_count),
                "is_host": request.user.pk == party.host_id,
                "is_member": party.memberships.filter(
                    user=request.user, left_at__isnull=True
                ).exists(),
            }
        }
    )


def active_memberships(party):
    return party.memberships.filter(left_at__isnull=True)


def can_view_members(party, user):
    """Allow only the Host or an active member; awaits team confirmation in S2-US6-D-01."""
    return party.host_id == user.pk or active_memberships(party).filter(user=user).exists()


def member_data(user, party):
    is_host = user.pk == party.host_id
    profile = getattr(user, "profile", None)
    # Legacy/local accounts may not have a profile. Never expose their login
    # identifier; use the same fallbacks as party_detail and join_requests.
    fallback = "ผู้จัดกิจกรรม" if is_host else "ผู้ใช้"
    return {
        "user_id": user.pk,
        "display_name": profile.display_name if profile else fallback,
        "role": "Host" if is_host else "Member",
    }


@never_cache
@require_authenticated_api
def party_members(request, party_id):
    if request.method != "GET":
        response = json_error("METHOD_NOT_ALLOWED", "รองรับเฉพาะ GET", 405)
        response["Allow"] = "GET"
        return response
    try:
        party = Party.objects.select_related("host__profile").get(pk=party_id)
    except Party.DoesNotExist:
        return json_error("NOT_FOUND", "ไม่พบกิจกรรมที่ต้องการ", 404)
    if not can_view_members(party, request.user):
        return json_error("FORBIDDEN", "เฉพาะผู้จัดกิจกรรมหรือสมาชิกเท่านั้นที่ดูรายชื่อสมาชิกได้", 403)

    rows = active_memberships(party).select_related("user__profile").order_by("joined_at", "pk")
    # The Host always comes from Party, so older Parties without a Host row still list them.
    members = [member_data(party.host, party)]
    members += [member_data(row.user, party) for row in rows if row.user_id != party.host_id]
    return JsonResponse({"data": {"members": members, "member_count": len(members)}})


@never_cache
@require_authenticated_api
def create_join_request(request, party_id):
    if request.method != "POST":
        response = json_error("METHOD_NOT_ALLOWED", "รองรับเฉพาะ POST", 405)
        response["Allow"] = "POST"
        return response

    # API-06 accepts only {} (or an empty body), never client-selected actors/status.
    if request.body:
        if request.content_type != "application/json":
            return json_error("INVALID_INPUT", "กรุณาส่ง JSON object ว่าง", 400)
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return json_error("INVALID_INPUT", "รูปแบบ JSON ไม่ถูกต้อง", 400)
        if not isinstance(payload, dict) or payload:
            return json_error("INVALID_INPUT", "รับเฉพาะ JSON object ว่าง", 400)

    try:
        join_request = submit_join_request(party_id=party_id, user=request.user)
    except JoinRequestError as error:
        return json_error(error.code, error.message, error.status)
    return JsonResponse(
        {
            "data": {
                "id": join_request.pk,
                "party_id": join_request.party_id,
                "status": join_request.status,
                "created_at": timezone.localtime(join_request.created_at).isoformat(),
            }
        },
        status=201,
    )


@never_cache
@require_university_user
def join_requests(request, party_id):
    """Read this Host's Pending requests; Party state only limits decisions."""
    if request.method != "GET":
        response = json_error("METHOD_NOT_ALLOWED", "รองรับเฉพาะ GET", 405)
        response["Allow"] = "GET"
        return response
    try:
        party = Party.objects.get(pk=party_id)
    except Party.DoesNotExist:
        return json_error("NOT_FOUND", "ไม่พบกิจกรรมที่ต้องการ", 404)
    if party.host_id != request.user.pk:
        return json_error("FORBIDDEN", "เฉพาะผู้จัดกิจกรรมเท่านั้นที่ดูคำขอได้", 403)
    rows = (
        JoinRequest.objects.filter(party=party, status=JoinRequest.Status.PENDING)
        .select_related("user__profile")
        .order_by("created_at", "pk")
    )
    return JsonResponse(
        {
            "data": [
                {
                    "id": row.pk,
                    "display_name": getattr(
                        getattr(row.user, "profile", None), "display_name", "ผู้ใช้"
                    ),
                    "created_at": timezone.localtime(row.created_at).isoformat(),
                }
                for row in rows
            ]
        }
    )


@never_cache
@require_university_user
def decide_join_request_api(request, party_id, request_id):
    if request.method != "POST":
        response = json_error("METHOD_NOT_ALLOWED", "รองรับเฉพาะ POST", 405)
        response["Allow"] = "POST"
        return response
    if request.content_type != "application/json":
        return json_error("INVALID_INPUT", "กรุณาส่งข้อมูลเป็น JSON", 400)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return json_error("INVALID_INPUT", "รูปแบบ JSON ไม่ถูกต้อง", 400)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"status"}
        or payload["status"] not in {"Approved", "Rejected"}
    ):
        return json_error("INVALID_INPUT", "ระบุสถานะ Approved หรือ Rejected", 400)
    try:
        join_request = decide_join_request(
            party_id=party_id,
            request_id=request_id,
            user=request.user,
            approved=payload["status"] == "Approved",
        )
    except PartyError as error:
        return json_error(error.code, error.message, error.status, error.fields)
    return JsonResponse({"data": {"id": join_request.pk, "status": join_request.status}})


@never_cache
@require_authenticated_api
@ensure_csrf_cookie
def my_join_request(request, party_id):
    if request.method != "GET":
        response = json_error("METHOD_NOT_ALLOWED", "รองรับเฉพาะ GET", 405)
        response["Allow"] = "GET"
        return response
    if not Party.objects.filter(pk=party_id).exists():
        return json_error("NOT_FOUND", "ไม่พบกิจกรรมที่ต้องการ", 404)
    join_request = JoinRequest.objects.filter(party_id=party_id, user=request.user).first()
    data = None
    if join_request is not None:
        data = {
            "id": join_request.pk,
            "status": join_request.status,
            "created_at": timezone.localtime(join_request.created_at).isoformat(),
        }
    return JsonResponse({"data": data})


def parse_party_datetimes(payload, fields):
    """Parse supplied datetime fields; record errors without filling absent fields."""
    for key in ("starts_at", "ends_at"):
        if key not in payload:
            continue
        value = payload[key]
        try:
            parsed = parse_datetime(value) if isinstance(value, str) and "T" in value else None
        except ValueError:
            parsed = None
        if parsed is None or timezone.is_naive(parsed):
            fields[key] = "กรุณาระบุ ISO 8601 datetime พร้อม timezone"
        else:
            payload[key] = parsed


@never_cache
@require_university_user
def create_party_api(request):
    if request.method == "GET":
        parties = (
            Party.objects.select_related("host__profile")
            .filter(cancelled_at__isnull=True, starts_at__gt=timezone.now())
            .annotate(
                active_member_count=Count(
                    "memberships", filter=Q(memberships__left_at__isnull=True)
                )
            )
            .filter(active_member_count__lt=F("capacity"))
            .order_by("starts_at")[:50]
        )
        data = []
        for party in parties:
            item = party_data(party, request.user)
            data.append(item)
        return JsonResponse({"data": data})
    if request.method != "POST":
        response = json_error("METHOD_NOT_ALLOWED", "รองรับเฉพาะ GET และ POST", 405)
        response["Allow"] = "GET, POST"
        return response
    if request.content_type != "application/json":
        return json_error("INVALID_INPUT", "กรุณาส่งข้อมูลเป็น JSON", 400)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return json_error("INVALID_INPUT", "รูปแบบ JSON ไม่ถูกต้อง", 400)
    if not isinstance(payload, dict):
        return json_error("INVALID_INPUT", "ข้อมูลต้องเป็น JSON object", 400)

    required = {"title", "sport_id", "venue_id", "starts_at", "ends_at", "capacity"}
    allowed = required | {"description"}
    fields = {key: "ไม่รองรับฟิลด์นี้" for key in payload.keys() - allowed}
    fields.update({key: "กรุณาระบุข้อมูล" for key in required - payload.keys()})
    parse_party_datetimes(payload, fields)
    if fields:
        return json_error("INVALID_INPUT", "ข้อมูลกิจกรรมไม่ถูกต้อง", 400, fields)
    payload.setdefault("description", "")
    try:
        party = create_party(user=request.user, **payload)
    except PartyError as error:
        return json_error(error.code, error.message, error.status, error.fields)
    return JsonResponse({"data": party_data(party, request.user)}, status=201)


@never_cache
@require_university_user
def cancel_party_api(request, party_id):
    if request.method != "POST":
        response = json_error("METHOD_NOT_ALLOWED", "รองรับเฉพาะ POST", 405)
        response["Allow"] = "POST"
        return response
    if request.content_type != "application/json":
        return json_error("INVALID_INPUT", "กรุณาส่ง JSON object ว่าง", 400)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return json_error("INVALID_INPUT", "รูปแบบ JSON ไม่ถูกต้อง", 400)
    if not isinstance(payload, dict) or payload:
        return json_error("INVALID_INPUT", "รับเฉพาะ JSON object ว่าง", 400)
    try:
        party = cancel_party(party_id=party_id, user=request.user)
    except PartyError as error:
        return json_error(error.code, error.message, error.status, error.fields)
    return JsonResponse(
        {
            "data": {
                "id": party.pk,
                "state": "Cancelled",
                "cancelled_at": timezone.localtime(party.cancelled_at).isoformat(),
            }
        }
    )


@never_cache
@require_university_user
def edit_party_api(request, party_id):
    if request.method != "PATCH":
        response = json_error("METHOD_NOT_ALLOWED", "รองรับเฉพาะ PATCH", 405)
        response["Allow"] = "PATCH"
        return response
    if request.content_type != "application/json":
        return json_error("INVALID_INPUT", "กรุณาส่งข้อมูลเป็น JSON", 400)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return json_error("INVALID_INPUT", "รูปแบบ JSON ไม่ถูกต้อง", 400)
    if not isinstance(payload, dict):
        return json_error("INVALID_INPUT", "ข้อมูลต้องเป็น JSON object", 400)
    fields = {key: "ไม่รองรับฟิลด์นี้" for key in payload.keys() - PARTY_EDIT_FIELDS}
    parse_party_datetimes(payload, fields)
    if fields:
        return json_error("INVALID_INPUT", "ข้อมูลกิจกรรมไม่ถูกต้อง", 400, fields)
    try:
        party = edit_party(party_id=party_id, user=request.user, changes=payload)
    except PartyError as error:
        return json_error(error.code, error.message, error.status, error.fields)
    return JsonResponse({"data": party_data(party, request.user)})
