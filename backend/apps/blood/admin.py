from django.contrib import admin

from .models import BloodUnit


@admin.register(BloodUnit)
class BloodUnitAdmin(admin.ModelAdmin):
    list_display = ["donation_number", "group", "component", "status", "expires_at", "location"]
    list_filter = ["group", "component", "status"]
    search_fields = ["donation_number"]
