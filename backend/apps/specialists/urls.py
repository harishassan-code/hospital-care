from django.urls import path

from . import views

urlpatterns = [
    path("", views.SpecialistListView.as_view(), name="specialist-list"),
    path("<int:pk>/", views.SpecialistDetailView.as_view(), name="specialist-detail"),
    path("<int:pk>/on-call/", views.OnCallWindowListView.as_view(), name="specialist-on-call"),
    path(
        "<int:pk>/on-call/<int:window>/",
        views.OnCallWindowDetailView.as_view(),
        name="specialist-on-call-detail",
    ),
]
