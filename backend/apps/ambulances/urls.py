from django.urls import path

from . import views

urlpatterns = [
    path("", views.AmbulanceListView.as_view(), name="ambulance-list"),
    path("<int:pk>/actions/", views.AmbulanceActionView.as_view(), name="ambulance-action"),
    path("available/", views.AvailableForDispatchView.as_view(), name="ambulance-available"),
    path("trips/", views.TripListView.as_view(), name="trip-list"),
    path("trips/<int:pk>/actions/", views.TripActionView.as_view(), name="trip-action"),
]
