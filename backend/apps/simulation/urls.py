from django.urls import path

from . import views

urlpatterns = [
    path("", views.SimulationView.as_view(), name="simulation"),
    path("tick/", views.TickView.as_view(), name="simulation-tick"),
    path("control/", views.ControlView.as_view(), name="simulation-control"),
    path("advance/", views.AdvanceView.as_view(), name="simulation-advance"),
]
