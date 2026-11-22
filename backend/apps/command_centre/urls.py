from django.urls import path

from .views import CommandCentreView

urlpatterns = [
    path("", CommandCentreView.as_view(), name="command-centre"),
]
