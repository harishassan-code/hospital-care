from django.urls import path

from apps.ambulances.views import TransferTripView

from .views import TransferActionView, TransferDetailView, TransferListView

urlpatterns = [
    path("", TransferListView.as_view(), name="transfer-list"),
    path("<int:pk>/", TransferDetailView.as_view(), name="transfer-detail"),
    path("<int:pk>/actions/", TransferActionView.as_view(), name="transfer-action"),
    path("<int:pk>/trip/", TransferTripView.as_view(), name="transfer-trip"),
]
