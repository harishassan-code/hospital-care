from django.urls import path

from . import views

urlpatterns = [
    path("", views.AuditListView.as_view(), name="audit-list"),
    path("export.csv", views.AuditExportView.as_view(), name="audit-export"),
]
