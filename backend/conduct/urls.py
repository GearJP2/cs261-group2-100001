from django.urls import path

from . import views

urlpatterns = [
    path(
        "parties/<int:party_id>/reviews",
        views.create_review,
        name="party-review-create",
    ),
    path("users/<int:user_id>/reviews", views.user_reviews, name="user-reviews"),
]
