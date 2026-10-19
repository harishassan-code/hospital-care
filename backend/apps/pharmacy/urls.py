from django.urls import path

from . import views

urlpatterns = [
    path("stock/", views.StockView.as_view(), name="pharmacy-stock"),
]
