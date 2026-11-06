from django.urls import path

from . import views

urlpatterns = [
    path(
        "parties/<int:party_id>/reviews",
        views.create_review,
        name="party-review-create",
    ),
]
