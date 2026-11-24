from django.contrib import admin

from .models import SimEvent, SimulationState


@admin.register(SimulationState)
class SimulationStateAdmin(admin.ModelAdmin):
    list_display = ["__str__", "enabled", "paused", "speed", "scenario", "progress", "fast_forward_to"]


@admin.register(SimEvent)
class SimEventAdmin(admin.ModelAdmin):
    list_display = ["at", "hospital", "kind", "message"]
    list_filter = ["kind"]
