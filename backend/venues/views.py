from accounts.decorators import require_university_user
from core.api import json_error
from django.http import JsonResponse
from django.views.decorators.cache import never_cache

from .models import Sport, Venue


class InvalidQuery(ValueError):
    pass


def positive_query(request, name, default=None, maximum=9223372036854775807):
    values = request.GET.getlist(name)
    if not values and default is not None:
        return default
    if len(values) != 1 or not values[0].isascii() or not values[0].isdigit():
        raise InvalidQuery(name)
    # Avoid unbounded integer conversion on client input.
    raw = values[0].lstrip("0")
    if not raw or len(raw) > len(str(maximum)):
        raise InvalidQuery(name)
    value = int(raw)
    if value > maximum:
        raise InvalidQuery(name)
    return value


def get_only(request):
    if request.method != "GET":
        response = json_error("METHOD_NOT_ALLOWED", "รองรับเฉพาะ GET", 405)
        response["Allow"] = "GET"
        return response
    return None


@never_cache
@require_university_user
def sports(request):
    error = get_only(request)
    if error is not None:
        return error
    return JsonResponse({"data": list(Sport.objects.order_by("id").values("id", "name"))})


@never_cache
@require_university_user
def venues(request):
    error = get_only(request)
    if error is not None:
        return error
    try:
        sport_id = positive_query(request, "sport_id")
        page = positive_query(request, "page", 1)
        page_size = positive_query(request, "page_size", 20, 100)
    except InvalidQuery as error:
        return json_error("INVALID_INPUT", "พารามิเตอร์ไม่ถูกต้อง", 400, {str(error): "ระบุจำนวนเต็มบวก"})
    queryset = Venue.objects.filter(is_active=True, venue_sports__sport_id=sport_id).order_by("id")
    total = queryset.count()
    offset = (page - 1) * page_size
    rows = (
        []
        if offset >= total
        else list(
            queryset.values("id", "name", "location_text", "venue_type")[
                offset : offset + page_size
            ]
        )
    )
    return JsonResponse({"data": rows, "page": page, "page_size": page_size, "total": total})


@never_cache
@require_university_user
def opening_hours(request, venue_id):
    error = get_only(request)
    if error is not None:
        return error
    venue = (
        Venue.objects.filter(pk=venue_id, is_active=True).first()
        if venue_id <= 9223372036854775807
        else None
    )
    if venue is None:
        return json_error("NOT_FOUND", "ไม่พบสนามที่เปิดใช้งาน", 404)
    return JsonResponse(
        {
            "data": {
                "venue_id": venue.pk,
                "timezone": "Asia/Bangkok",
                "intervals": [
                    {
                        "weekday": row.weekday,
                        "opens_at": row.opens_at.isoformat(),
                        "closes_at": row.closes_at.isoformat(),
                    }
                    for row in venue.opening_hours.order_by("weekday", "opens_at")
                ],
            }
        }
    )
