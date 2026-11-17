from django.urls import path

from . import views

urlpatterns = [
    path("", views.EquipmentListView.as_view(), name="equipment-list"),
    path("<int:pk>/actions/", views.EquipmentActionView.as_view(), name="equipment-action"),
]
