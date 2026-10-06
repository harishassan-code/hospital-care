from django.contrib import admin

from .models import Batch, Medicine


class BatchInline(admin.TabularInline):
    model = Batch
    extra = 0


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ["name", "strength", "form", "category", "reorder_level", "high_alert", "controlled"]
    list_filter = ["category", "high_alert", "controlled"]
    search_fields = ["name", "code"]
    inlines = [BatchInline]
