from django.urls import path, re_path

from . import views

KINDS = "(?P<kind>departments|wards|locations)"

urlpatterns = [
    path("", views.HospitalListView.as_view(), name="hospital-list"),
    path("capabilities/", views.CapabilityListView.as_view(), name="capability-list"),
    path("<int:pk>/", views.HospitalDetailView.as_view(), name="hospital-detail"),
    re_path(rf"^(?P<pk>\d+)/{KINDS}/$", views.StructureListView.as_view(), name="hospital-structure"),
    re_path(
        rf"^(?P<pk>\d+)/{KINDS}/(?P<item>\d+)/$",
        views.StructureItemView.as_view(),
        name="hospital-structure-item",
    ),
]
