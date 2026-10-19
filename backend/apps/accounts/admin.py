from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class HospitalUserAdmin(UserAdmin):
    list_display = ["email", "first_name", "last_name", "role", "hospital", "is_active", "is_staff"]
    list_filter = ["role", "hospital", "is_active", "is_staff", "is_superuser"]
    search_fields = ["email", "first_name", "last_name", "phone"]
    ordering = ["email"]
    fieldsets = (*UserAdmin.fieldsets, ("Hospital", {"fields": ("role", "hospital", "phone")}))
    add_fieldsets = (
        *UserAdmin.add_fieldsets,
        ("Hospital", {"fields": ("first_name", "last_name", "email", "role", "hospital", "phone")}),
    )
