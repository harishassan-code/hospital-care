from django.contrib import admin

from .models import OnCallWindow, Specialist


class ReadOnlyAdmin(admin.ModelAdmin):
    """Read-only (B16): profiles and windows are changed in the app, where each change is checked and
    audit-logged. An admin write here would skip both."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Specialist)
class SpecialistAdmin(ReadOnlyAdmin):
    list_display = ["name", "specialty", "hospital", "is_active"]
    list_filter = ["hospital", "is_active"]
    search_fields = ["name", "specialty"]


@admin.register(OnCallWindow)
class OnCallWindowAdmin(ReadOnlyAdmin):
    list_display = ["specialist", "starts_at", "ends_at"]
    list_filter = ["specialist__hospital"]
    search_fields = ["specialist__name"]
