from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["created_at", "kind", "severity", "title", "hospital", "roles"]
    list_filter = ["severity", "kind", "hospital"]
