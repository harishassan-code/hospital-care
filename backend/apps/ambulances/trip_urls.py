from django.urls import path

from . import views

urlpatterns = [
    path("<int:pk>/actions/", views.TripActionView.as_view(), name="trip-action"),
]
