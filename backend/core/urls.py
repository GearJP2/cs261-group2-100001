from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_page, name="login-page"),
    path("parties/new/", views.party_create_page, name="party-create-page"),
    path("parties/<int:party_id>/", views.party_detail_page, name="party-detail-page"),
    path("parties/<int:party_id>/edit/", views.party_edit_page, name="party-edit-page"),
    path("users/<int:user_id>/", views.public_profile_page, name="public-profile-page"),
    path("health/live/", views.live, name="health-live"),
    path("health/ready/", views.ready, name="health-ready"),
    path("my-parties/", views.my_parties_page, name="my-parties-page"),
]
