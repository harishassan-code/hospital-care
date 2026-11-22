from django.urls import path

from .views import ReportExportView, ReportView

urlpatterns = [
    path("", ReportView.as_view(), name="reports"),
    path("export/", ReportExportView.as_view(), name="reports-export"),
]
