from django.contrib import admin

from .models import BloodUnit, DonationAppointment, Donor, TestResult


class TestResultInline(admin.TabularInline):
    model = TestResult
    extra = 0
    readonly_fields = ["recorded_at", "recorded_by"]


@admin.register(BloodUnit)
class BloodUnitAdmin(admin.ModelAdmin):
    list_display = ["donation_number", "group", "component", "status", "expires_at", "location", "donor"]
    list_filter = ["group", "component", "status"]
    search_fields = ["donation_number", "donor__code"]
    raw_id_fields = ["donor"]
    inlines = [TestResultInline]


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    list_display = ["code", "full_name", "blood_group", "phone", "deferral_reason", "deferred_until"]
    list_filter = ["blood_group"]
    search_fields = ["code", "full_name", "phone"]


@admin.register(DonationAppointment)
class DonationAppointmentAdmin(admin.ModelAdmin):
    list_display = ["starts_at", "donor", "hospital", "status"]
    list_filter = ["status", "hospital"]
    raw_id_fields = ["donor"]
