from django.urls import path

from . import views

urlpatterns = [
    path("", views.AmbulanceListView.as_view(), name="ambulance-list"),
    path("<int:pk>/actions/", views.AmbulanceActionView.as_view(), name="ambulance-action"),
]
