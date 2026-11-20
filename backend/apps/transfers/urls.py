from django.urls import path

from .views import TransferActionView, TransferDetailView, TransferListView, TransferTripView

urlpatterns = [
    path("", TransferListView.as_view(), name="transfer-list"),
    path("<int:pk>/", TransferDetailView.as_view(), name="transfer-detail"),
    path("<int:pk>/actions/", TransferActionView.as_view(), name="transfer-action"),
    path("<int:pk>/trips/", TransferTripView.as_view(), name="transfer-trips"),
]
