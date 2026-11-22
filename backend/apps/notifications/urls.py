from django.urls import path

from .views import NotificationListView, NotificationReadView, NotificationUnreadCountView

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("unread-count/", NotificationUnreadCountView.as_view(), name="notification-unread-count"),
    path("<int:pk>/read/", NotificationReadView.as_view(), name="notification-read"),
]
