from accounts.decorators import require_university_user
from accounts.models import UserProfile, UserSportInterest
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
def home(request):
    return render(request, "home.html")


@require_GET
def login_page(request):
    return render(request, "login.html")


@require_GET
def party_create_page(request):
    return render(
        request,
        "party_form.html",
        {
            "mode": "create",
            "sport_id": request.GET.get("sport_id", ""),
            "venue_id": request.GET.get("venue_id", ""),
        },
    )


@require_GET
def party_detail_page(request, party_id):
    return render(request, "party_detail.html", {"party_id": party_id})


@require_GET
def party_edit_page(request, party_id):
    return render(request, "party_form.html", {"mode": "edit", "party_id": party_id})


@require_GET
@never_cache
@require_university_user
def public_profile_page(request, user_id):
    """Render only the public fields exposed by the US8 profile contract."""
    profile = UserProfile.objects.filter(user_id=user_id).first()
    if profile is None:
        return render(request, "profile.html", {"profile": None}, status=404)

    interests = UserSportInterest.objects.filter(user_id=user_id).order_by("sport_id")
    return render(
        request,
        "profile.html",
        {
            "profile": {
                "name": profile.display_name,
                "credit": profile.credit_score,
                "interests": list(interests.values_list("sport__name", flat=True)),
            }
        },
    )


@require_GET
def live(request):
    return JsonResponse({"status": "ok"})


@require_GET
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        # Return a stable error without leaking connection details or credentials.
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})


def my_parties_page(request):
    return render(request, "myparty.html")