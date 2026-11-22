from django.contrib import admin

from .models import Ambulance, Trip


@admin.register(Ambulance)
class AmbulanceAdmin(admin.ModelAdmin):
    list_display = ["identifier", "ambulance_type", "plate", "status", "hospital"]
    list_filter = ["ambulance_type", "status", "hospital"]
    search_fields = ["identifier", "plate"]


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ["id", "ambulance", "transfer", "status", "dispatched_at"]
    list_filter = ["status"]
