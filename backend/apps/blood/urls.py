from django.urls import path

from . import views

urlpatterns = [
    path("units/", views.BloodUnitListView.as_view(), name="blood-units"),
    path("units/<str:unit_id>/", views.BloodUnitDetailView.as_view(), name="blood-unit"),
    path("units/<str:unit_id>/tests/", views.BloodUnitTestView.as_view(), name="blood-unit-tests"),
    path("units/<str:unit_id>/actions/", views.BloodUnitActionView.as_view(), name="blood-unit-action"),
    path("stock/", views.BloodStockView.as_view(), name="blood-stock"),
    path("donors/", views.DonorListView.as_view(), name="blood-donors"),
    path("donors/<str:donor_id>/", views.DonorDetailView.as_view(), name="blood-donor"),
    path(
        "donors/<str:donor_id>/screening/", views.DonorScreeningView.as_view(), name="blood-donor-screening"
    ),
    path("appointments/", views.AppointmentListView.as_view(), name="blood-appointments"),
    path(
        "appointments/<int:appointment_id>/cancel/",
        views.AppointmentCancelView.as_view(),
        name="blood-appointment-cancel",
    ),
]
