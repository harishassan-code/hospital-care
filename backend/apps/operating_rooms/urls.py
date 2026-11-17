from django.urls import path

from . import views

urlpatterns = [
    path("", views.OperatingRoomListView.as_view(), name="operating-room-list"),
    path("<int:pk>/actions/", views.OperatingRoomActionView.as_view(), name="operating-room-action"),
    path("schedule/", views.OperatingRoomScheduleView.as_view(), name="operating-room-schedule"),
    path("bookings/", views.OrBookingListView.as_view(), name="operating-room-bookings"),
    path(
        "bookings/<int:pk>/cancel/", views.OrBookingCancelView.as_view(), name="operating-room-booking-cancel"
    ),
]
