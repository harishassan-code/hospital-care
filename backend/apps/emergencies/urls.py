from django.urls import path

from . import views

urlpatterns = [
    path("status/", views.PublicStatusView.as_view(), name="public-status"),
]
