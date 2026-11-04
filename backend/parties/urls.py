from django.urls import path

from . import views

urlpatterns = [
    path("parties", views.create_party_api, name="party-create"),
    path("parties/<int:party_id>/cancel", views.cancel_party_api, name="party-cancel"),
    path("parties/<int:party_id>", views.party_detail, name="party-detail"),
    path("parties/<int:party_id>/members", views.party_members, name="party-members"),
    path(
        "parties/<int:party_id>/join-requests",
        views.create_join_request,
        name="party-join-request-create",
    ),
    path(
        "parties/<int:party_id>/join-requests/me",
        views.my_join_request,
        name="party-join-request-me",
    ),
    path(
        "parties/<int:party_id>/join-requests/pending",
        views.join_requests,
        name="party-join-request-list",
    ),
    path(
        "parties/<int:party_id>/join-requests/<int:request_id>/decision",
        views.decide_join_request_api,
        name="party-join-request-decision",
    ),
]
