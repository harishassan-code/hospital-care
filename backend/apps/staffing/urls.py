from django.urls import path

from . import views

urlpatterns = [
    path("", views.StaffingView.as_view(), name="staffing"),
    path("shifts/<int:pk>/actions/", views.ShiftActionView.as_view(), name="staffing-shift-action"),
]
