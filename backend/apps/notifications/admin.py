from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Read-only. `notify` writes the rows and the API only sets `read_at`, so nothing adds, changes or
    deletes one here."""

    list_display = ["kind", "severity", "user", "message", "created_at", "read_at"]
    list_filter = ["kind", "severity"]
    search_fields = ["message", "user__email"]
    readonly_fields = [f.name for f in Notification._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
