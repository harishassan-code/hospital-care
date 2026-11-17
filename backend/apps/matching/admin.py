from django.contrib import admin

from .models import Allocation


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    """Read-only (story #45): an allocation is the permanent record of who received what. Nothing adds,
    changes or deletes one, here or in the app."""

    list_display = ["request", "request_item", "hospital", "allocated_by", "at"]
    list_filter = ["hospital"]
    search_fields = ["request__reference"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
