from django.contrib import admin

from .models import Bed, Capability, Department, DoctorShift, Hospital, StorageLocation, Ward


@admin.register(Capability)
class CapabilityAdmin(admin.ModelAdmin):
    """The managed list of hospital capabilities (story 1.3)."""

    list_display = ["name", "code"]


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ["name", "type", "is_active", "address"]
    list_filter = ["type", "is_active", "capabilities"]
    search_fields = ["name", "address"]
    filter_horizontal = ["capabilities"]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "hospital"]
    list_filter = ["hospital"]


@admin.register(StorageLocation)
class StorageLocationAdmin(admin.ModelAdmin):
    list_display = ["name", "hospital"]
    list_filter = ["hospital"]


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "hospital", "kind", "sort_order"]
    list_filter = ["hospital"]


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = [
        "label",
        "ward",
        "hospital",
        "status",
        "status_since",
        "patient_initials",
        "expected_discharge",
    ]
    list_filter = ["hospital", "ward", "status", "isolation"]
    search_fields = ["label"]


@admin.register(DoctorShift)
class DoctorShiftAdmin(admin.ModelAdmin):
    list_display = ["name", "department", "start", "end", "is_active"]
    list_filter = ["department", "is_active"]
