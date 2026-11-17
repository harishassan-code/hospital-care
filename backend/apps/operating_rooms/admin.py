from django.contrib import admin

from .models import OperatingRoom


@admin.register(OperatingRoom)
class OperatingRoomAdmin(admin.ModelAdmin):
    list_display = ["name", "location", "status", "hospital"]
    list_filter = ["status", "hospital"]
    search_fields = ["name", "location"]
