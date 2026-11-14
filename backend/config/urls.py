from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("accounts.urls")),
    path("", include("core.urls")),
    path("api/v1/", include("parties.urls")),
    path("api/v1/", include("conduct.urls")),
    path("venues/", include("venues.ui_urls")),
    path("api/v1/", include("venues.urls")),
]
