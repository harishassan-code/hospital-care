from django.contrib import admin

from .models import Shift, StaffMember


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ["name", "role", "department", "hospital", "is_active"]
    list_filter = ["hospital", "role", "department", "is_active"]
    search_fields = ["name"]


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ["staff", "hospital", "starts_at", "ends_at", "clocked_in_at", "clocked_out_at"]
    list_filter = ["hospital"]
    date_hierarchy = "starts_at"
