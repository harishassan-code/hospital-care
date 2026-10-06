from django.contrib import admin

from .models import Bed, DoctorShift, Ward


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "kind", "sort_order"]


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ["label", "ward", "status", "status_since", "patient_initials", "expected_discharge"]
    list_filter = ["ward", "status", "isolation"]
    search_fields = ["label"]


@admin.register(DoctorShift)
class DoctorShiftAdmin(admin.ModelAdmin):
    list_display = ["name", "department", "start", "end", "is_active"]
    list_filter = ["department", "is_active"]
