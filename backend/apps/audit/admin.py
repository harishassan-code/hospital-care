from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only. Search and export arrive with story 8.1 Audit Search & Export (Sprint 8)."""

    list_display = ["at", "actor_email", "action", "target_repr", "reason"]
    list_filter = ["action", "target_type"]
    search_fields = ["actor_email", "target_repr", "target_id"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
