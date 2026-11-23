from django.contrib import admin

from .models import MetricSnapshot


@admin.register(MetricSnapshot)
class MetricSnapshotAdmin(admin.ModelAdmin):
    list_display = ["hospital", "metric", "at", "value"]
    list_filter = ["hospital", "metric"]
    date_hierarchy = "at"
