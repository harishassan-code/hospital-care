from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/public/", include("apps.emergencies.urls")),
    path("api/beds/", include("apps.hospitals.urls")),
    path("api/blood/", include("apps.blood.urls")),
    path("api/pharmacy/", include("apps.pharmacy.urls")),
]
