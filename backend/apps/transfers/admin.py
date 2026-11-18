from django.contrib import admin

from .models import Transfer, TransferStatusChange


class TransferStatusChangeInline(admin.TabularInline):
    """The transfer's history, read-only: moves are made in the app so they're audit-logged."""

    model = TransferStatusChange
    extra = 0
    can_delete = False
    readonly_fields = ["from_status", "to_status", "action", "note", "actor", "at"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    """Read-only (stories #47 to #49): transfers are asked, answered and received in the app, where every
    move is checked, kept in the history and audit-logged. Nothing adds, changes or deletes one here."""

    list_display = ["id", "request_item", "supplier", "receiver", "quantity", "status", "created_at"]
    list_filter = ["status", "supplier", "receiver"]
    search_fields = ["request_item__request__reference"]
    readonly_fields = [
        "request_item",
        "supplier",
        "receiver",
        "quantity",
        "status",
        "reason",
        "requested_by",
        "created_at",
        "reservations",
    ]
    inlines = [TransferStatusChangeInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
