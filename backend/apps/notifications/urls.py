from django.urls import path

from . import views

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="notification-list"),
    path("unread-count/", views.UnreadCountView.as_view(), name="notification-unread-count"),
    path("read-all/", views.ReadAllView.as_view(), name="notification-read-all"),
    path("<int:pk>/read/", views.ReadView.as_view(), name="notification-read"),
    path("<int:pk>/acknowledge/", views.AcknowledgeView.as_view(), name="notification-acknowledge"),
]
