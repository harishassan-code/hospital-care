from django.contrib import admin

from .models import Ambulance


@admin.register(Ambulance)
class AmbulanceAdmin(admin.ModelAdmin):
    list_display = ["identifier", "type", "status", "hospital"]
    list_filter = ["type", "status", "hospital"]
    search_fields = ["identifier"]
