from django.contrib import admin

from .models import Equipment


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ["identifier", "equipment_type", "name", "location", "status", "hospital"]
    list_filter = ["equipment_type", "status", "hospital"]
    search_fields = ["identifier", "name", "location"]
