from django.urls import path

from . import views

urlpatterns = [
    path("entries/", views.AuditEntryListView.as_view(), name="audit-entry-list"),
    path("entries/export/", views.AuditExportView.as_view(), name="audit-entry-export"),
]
