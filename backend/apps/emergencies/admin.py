from django.contrib import admin

from .models import EmergencyStatus


@admin.register(EmergencyStatus)
class EmergencyStatusAdmin(admin.ModelAdmin):
    list_display = ["status", "wait_minutes", "waiting_count", "updated_at"]
