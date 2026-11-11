import json

from core.api import json_error, require_authenticated_api
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from parties.services import PartyError
from venues.views import InvalidQuery, get_only, positive_query

from .services import average_rating, list_reviews, submit_review

REVIEW_FIELDS = frozenset({"reviewee_id", "rating", "comment"})
MAX_COMMENT_LENGTH = 500
# PostgreSQL bigint upper bound of the user primary key.
MAX_USER_ID = 9_223_372_036_854_775_807
DEFAULT_REVIEW_PAGE_SIZE = 20
MAX_REVIEW_PAGE_SIZE = 100


def reviewer_display_name(user):
    # Never expose a login identifier as a replacement display name.
    return getattr(getattr(user, "profile", None), "display_name", "ผู้ใช้")


def comment_error(comment):
    if not isinstance(comment, str) or not comment.strip():
        return "กรุณาระบุความคิดเห็น"
    if len(comment.strip()) > MAX_COMMENT_LENGTH:
        return f"ความคิดเห็นต้องไม่เกิน {MAX_COMMENT_LENGTH} ตัวอักษร"
    if "\x00" in comment:
        return "ข้อความต้องไม่มีอักขระ NUL"
    try:
        # JSON can carry lone surrogates, which PostgreSQL text cannot store.
        comment.encode("utf-8")
    except UnicodeEncodeError:
        return "ข้อความมีอักขระที่ไม่รองรับ"
    return None


def validate_review_payload(payload):
    fields = {key: "ไม่รองรับฟิลด์นี้" for key in payload.keys() - REVIEW_FIELDS}
    fields.update({key: "กรุณาระบุข้อมูล" for key in REVIEW_FIELDS - payload.keys()})
    if "reviewee_id" in payload and (
        type(payload["reviewee_id"]) is not int or not 1 <= payload["reviewee_id"] <= MAX_USER_ID
    ):
        fields["reviewee_id"] = "กรุณาระบุผู้ที่ต้องการรีวิว"
    if "rating" in payload and (
        type(payload["rating"]) is not int or not 1 <= payload["rating"] <= 5
    ):
        fields["rating"] = "คะแนนต้องเป็นจำนวนเต็มตั้งแต่ 1 ถึง 5"
    if "comment" in payload:
        error = comment_error(payload["comment"])
        if error:
            fields["comment"] = error
    return fields


@never_cache
@require_authenticated_api
def create_review(request, party_id):
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
    if not isinstance(payload, dict):
        return json_error("INVALID_INPUT", "ข้อมูลต้องเป็น JSON object", 400)

    fields = validate_review_payload(payload)
    if fields:
        return json_error("INVALID_INPUT", "ข้อมูลรีวิวไม่ถูกต้อง", 400, fields)
    try:
        review = submit_review(
            party_id=party_id,
            reviewer=request.user,
            reviewee_id=payload["reviewee_id"],
            rating=payload["rating"],
            comment=payload["comment"].strip(),
        )
    except PartyError as error:
        return json_error(error.code, error.message, error.status, error.fields)
    return JsonResponse(
        {
            "data": {
                "review": {
                    "id": review.pk,
                    "party_id": review.party_id,
                    "reviewer": {
                        "id": review.reviewer_id,
                        "display_name": reviewer_display_name(request.user),
                    },
                    "reviewee_id": review.reviewee_id,
                    "rating": review.rating,
                    "comment": review.comment,
                    "created_at": timezone.localtime(review.created_at).isoformat(),
                }
            }
        },
        status=201,
    )


@never_cache
@require_authenticated_api
def user_reviews(request, user_id):
    error = get_only(request)
    if error is not None:
        return error
    try:
        page = positive_query(request, "page", 1)
        page_size = positive_query(
            request, "page_size", DEFAULT_REVIEW_PAGE_SIZE, MAX_REVIEW_PAGE_SIZE
        )
    except InvalidQuery as error:
        return json_error("INVALID_INPUT", "พารามิเตอร์ไม่ถูกต้อง", 400, {str(error): "ระบุจำนวนเต็มบวก"})
    try:
        profile, reviews, total = list_reviews(user_id, page, page_size)
    except PartyError as error:
        return json_error(error.code, error.message, error.status, error.fields)
    return JsonResponse(
        {
            "data": {
                "user_id": profile.user_id,
                "average_rating": average_rating(profile),
                "rating_count": profile.rating_count,
                "reviews": [
                    {
                        "id": review.pk,
                        "rating": review.rating,
                        "comment": review.comment,
                        "reviewer": {"display_name": reviewer_display_name(review.reviewer)},
                        "created_at": timezone.localtime(review.created_at).isoformat(),
                    }
                    for review in reviews
                ],
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        }
    )
