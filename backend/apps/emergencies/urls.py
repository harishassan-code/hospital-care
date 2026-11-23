from django.urls import path

from . import public_views

urlpatterns = [
    path("network/", public_views.PublicNetworkView.as_view(), name="public-network"),
    path("hospitals/", public_views.PublicHospitalListView.as_view(), name="public-hospitals"),
    path("hospitals/<int:pk>/", public_views.PublicHospitalDetailView.as_view(), name="public-hospital"),
]
