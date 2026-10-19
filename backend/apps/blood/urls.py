from django.urls import path

from . import views

urlpatterns = [
    path("units/", views.BloodUnitListView.as_view(), name="blood-units"),
]
