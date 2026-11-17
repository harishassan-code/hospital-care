from django.urls import path

from . import views

urlpatterns = [
    path("", views.HeldReservationListView.as_view(), name="reservations"),
    path("allocate/", views.ReservationAllocateManyView.as_view(), name="reservations-allocate-many"),
    path("<int:pk>/allocate/", views.ReservationAllocateView.as_view(), name="reservation-allocate"),
]
