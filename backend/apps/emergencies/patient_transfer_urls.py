from django.urls import path

from .patient_transfer_views import PatientTransferActionView, PatientTransferListView

# Mounted at the API root (config/urls.py), not under /emergencies/: there, the case route
# `<str:reference>/` would catch the list.
urlpatterns = [
    path("", PatientTransferListView.as_view(), name="patient-transfer-list"),
    path("<int:pk>/actions/", PatientTransferActionView.as_view(), name="patient-transfer-action"),
]
