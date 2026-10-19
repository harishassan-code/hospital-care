from django.urls import path

from . import views

urlpatterns = [
    path("", views.BedBoardView.as_view(), name="bed-board"),
    path("<str:label>/actions/", views.BedActionView.as_view(), name="bed-action"),
]
