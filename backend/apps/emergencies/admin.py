from django.contrib import admin

from .models import EmergencyRequest, EmergencyStatus, RequestItem


@admin.register(EmergencyStatus)
class EmergencyStatusAdmin(admin.ModelAdmin):
    list_display = ["status", "wait_minutes", "waiting_count", "updated_at"]


class RequestItemInline(admin.TabularInline):
    model = RequestItem
    extra = 0


@admin.register(EmergencyRequest)
class EmergencyRequestAdmin(admin.ModelAdmin):
    """Read-mostly: cases are opened and moved in the app so they're audit-logged and in the timeline."""

    list_display = ["reference", "severity", "status", "hospital", "created_at"]
    list_filter = ["severity", "status", "hospital"]
    search_fields = ["reference"]
    readonly_fields = ["reference", "status", "created_by", "created_at"]
    inlines = [RequestItemInline]
