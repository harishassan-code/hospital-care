"""Stories 1.3: hospital registration, capability profile and structure (api-contracts.md)."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.blood.models import BloodUnit
from apps.hospitals.models import Bed, Capability, Department, Hospital, StorageLocation, Ward

pytestmark = pytest.mark.django_db

VALID = {
    "name": "Northside Hospital",
    "type": "hospital",
    "address": "North Nazimabad, Karachi",
    "latitude": 24.942,
    "longitude": 67.0347,
}


@pytest.fixture
def admin(client_as):
    return client_as(Role.ADMIN)


def structure_url(hospital, kind, item=None):
    if item is None:
        return reverse("hospital-structure", kwargs={"pk": hospital.pk, "kind": kind})
    return reverse("hospital-structure-item", kwargs={"pk": hospital.pk, "kind": kind, "item": item})


class TestRegistration:
    def test_capabilities_are_a_managed_list_seeded_by_migration(self, admin):
        codes = [c["code"] for c in admin.get(reverse("capability-list")).json()]
        assert {"trauma", "nicu", "bloodBank", "icu"} <= set(codes)

    def test_admin_registers_a_hospital_with_capabilities(self, admin):
        response = admin.post(
            reverse("hospital-list"), {**VALID, "capabilities": ["trauma", "nicu"]}, format="json"
        )
        assert response.status_code == 201
        data = response.json()
        assert data == {
            **VALID,
            "id": data["id"],
            "phone": "",
            "isActive": True,
            "capabilities": ["nicu", "trauma"],  # in the managed list's order (by name)
        }
        entry = AuditLog.objects.get(action="hospital.created")
        assert entry.target_id == str(data["id"]) and entry.after["name"] == "Northside Hospital"

    def test_blood_banks_register_too(self, admin):
        response = admin.post(reverse("hospital-list"), {**VALID, "type": "bloodBank"}, format="json")
        assert response.status_code == 201 and response.json()["type"] == "bloodBank"

    @pytest.mark.parametrize(
        ("change", "field"),
        [
            ({"name": ""}, "name"),
            ({"address": "  "}, "address"),
            ({"type": "clinic"}, "type"),
            ({"latitude": 90.5}, "latitude"),
            ({"longitude": -181}, "longitude"),
            ({"latitude": 24.1234567}, "latitude"),
            ({"phone": "call us"}, "phone"),
            ({"capabilities": ["teleportation"]}, "capabilities"),
        ],
    )
    def test_invalid_fields_are_refused_on_the_field(self, admin, change, field):
        response = admin.post(reverse("hospital-list"), {**VALID, **change}, format="json")
        assert response.status_code == 400 and field in response.json()
        assert not Hospital.objects.exists()

    def test_missing_fields_are_listed(self, admin):
        response = admin.post(reverse("hospital-list"), {}, format="json")
        assert set(response.json()) == {"name", "address", "latitude", "longitude"}

    def test_names_are_unique_whatever_the_case(self, admin, make_hospital):
        make_hospital("Northside Hospital")
        response = admin.post(
            reverse("hospital-list"), {**VALID, "name": "NORTHSIDE hospital"}, format="json"
        )
        assert response.json() == {"name": ["A hospital with this name is already registered."]}

    def test_edit_logs_only_what_changed(self, admin, make_hospital):
        hospital = make_hospital()
        url = reverse("hospital-detail", args=[hospital.pk])
        response = admin.patch(url, {"phone": "+92 21 111 000 111", "name": hospital.name}, format="json")
        assert response.status_code == 200 and response.json()["phone"] == "+92 21 111 000 111"
        entry = AuditLog.objects.get(action="hospital.updated")
        assert (entry.before, entry.after) == ({"phone": ""}, {"phone": "+92 21 111 000 111"})

    def test_deactivated_hospitals_stay_listed_and_marked(self, admin, client_as, make_hospital):
        hospital = make_hospital()
        admin.patch(reverse("hospital-detail", args=[hospital.pk]), {"isActive": False}, format="json")
        hospital.refresh_from_db()
        assert hospital.is_active is False
        listed = client_as(Role.DOCTOR, email="doc@example.com").get(reverse("hospital-list")).json()
        assert [(h["name"], h["isActive"]) for h in listed] == [(hospital.name, False)]
        assert list(Hospital.objects.filter(is_active=True)) == []  # what matching (Sprint 6) will query

    def test_no_one_can_delete_a_hospital(self, admin, make_hospital):
        hospital = make_hospital()
        assert admin.delete(reverse("hospital-detail", args=[hospital.pk])).status_code == 405

    @pytest.mark.parametrize("role", [Role.DOCTOR, Role.NURSE, Role.BLOOD_BANK, Role.PHARMACIST])
    def test_other_roles_view_but_cannot_change(self, client_as, make_hospital, role):
        hospital = make_hospital()
        client = client_as(role)
        assert client.get(reverse("hospital-detail", args=[hospital.pk])).status_code == 200
        assert client.post(reverse("hospital-list"), VALID, format="json").status_code == 403
        assert (
            client.patch(
                reverse("hospital-detail", args=[hospital.pk]), {"name": "X"}, format="json"
            ).status_code
            == 403
        )
        assert (
            client.post(structure_url(hospital, "departments"), {"name": "X"}, format="json").status_code
            == 403
        )


class TestStructure:
    def test_detail_lists_capabilities_and_structure(self, admin, make_hospital):
        hospital = make_hospital()
        hospital.capabilities.set(Capability.objects.filter(code="trauma"))
        dept = Department.objects.create(hospital=hospital, name="Surgery")
        ward = Ward.objects.create(
            code="sb", name="Surgical B", kind="General surgery", hospital=hospital, department=dept
        )
        Bed.objects.create(ward=ward, label="SB-01")
        StorageLocation.objects.create(hospital=hospital, name="Blood fridge 1")
        data = admin.get(reverse("hospital-detail", args=[hospital.pk])).json()
        assert data["capabilities"] == ["trauma"]
        assert data["departments"] == [{"id": dept.pk, "name": "Surgery"}]
        assert data["wards"] == [
            {
                "id": ward.pk,
                "code": "sb",
                "name": "Surgical B",
                "kind": "General surgery",
                "departmentId": dept.pk,
                "bedCount": 1,
            }
        ]
        assert [loc["name"] for loc in data["locations"]] == ["Blood fridge 1"]

    def test_add_items_that_belong_to_exactly_one_hospital(self, admin, make_hospital):
        hospital = make_hospital()
        dept = admin.post(structure_url(hospital, "departments"), {"name": " Cardiology "}, format="json")
        assert dept.status_code == 201 and dept.json()["name"] == "Cardiology"
        ward = admin.post(
            structure_url(hospital, "wards"),
            {"name": "Coronary care", "kind": "Cardiology", "departmentId": dept.json()["id"]},
            format="json",
        ).json()
        assert ward["code"] == f"h{hospital.pk}-coronary-care" and ward["bedCount"] == 0
        loc = admin.post(structure_url(hospital, "locations"), {"name": "Main store"}, format="json")
        assert loc.status_code == 201
        assert Ward.objects.get(pk=ward["id"]).hospital == hospital
        assert StorageLocation.objects.get(pk=loc.json()["id"]).hospital == hospital
        assert {e.action for e in AuditLog.objects.all()} == {
            "department.created",
            "ward.created",
            "location.created",
        }

    def test_names_are_unique_within_a_hospital_only(self, admin, make_hospital):
        here, there = make_hospital("Here"), make_hospital("There")
        admin.post(structure_url(here, "departments"), {"name": "Surgery"}, format="json")
        again = admin.post(structure_url(here, "departments"), {"name": "SURGERY"}, format="json")
        assert again.json() == {"name": ["This hospital already has one with that name."]}
        assert (
            admin.post(structure_url(there, "departments"), {"name": "Surgery"}, format="json").status_code
            == 201
        )

    def test_a_ward_cannot_use_another_hospitals_department(self, admin, make_hospital):
        here, there = make_hospital("Here"), make_hospital("There")
        foreign = Department.objects.create(hospital=there, name="Surgery")
        response = admin.post(
            structure_url(here, "wards"),
            {"name": "W", "kind": "General", "departmentId": foreign.pk},
            format="json",
        )
        assert response.json() == {"departmentId": ["Choose a department of this hospital."]}

    def test_ward_codes_stay_unique(self, admin, make_hospital):
        here = make_hospital()
        Ward.objects.create(
            code=f"h{here.pk}-icu", name="Old ICU", kind="x"
        )  # e.g. a ward from before Sprint 2
        ward = admin.post(
            structure_url(here, "wards"), {"name": "ICU", "kind": "Intensive care"}, format="json"
        )
        assert ward.json()["code"] == f"h{here.pk}-icu-2"

    def test_remove_refuses_items_still_in_use(self, admin, make_hospital):
        hospital = make_hospital()
        ward = Ward.objects.create(code="w", name="W", kind="General", hospital=hospital)
        Bed.objects.create(ward=ward, label="W-01")
        fridge = StorageLocation.objects.create(hospital=hospital, name="Blood fridge 1")
        now = timezone.now()
        BloodUnit.objects.create(
            donation_number="G7731 26 000001",
            group="O+",
            component="redCells",
            collected_at=now,
            expires_at=now + timezone.timedelta(days=42),
            location="Blood fridge 1",
            hospital=hospital,
            storage_location=fridge,
        )
        ward_response = admin.delete(structure_url(hospital, "wards", ward.pk))
        assert ward_response.status_code == 409
        assert ward_response.json() == {"detail": "This ward still has beds. Move or remove them first."}
        assert admin.delete(structure_url(hospital, "locations", fridge.pk)).status_code == 409
        assert (
            Ward.objects.filter(pk=ward.pk).exists() and StorageLocation.objects.filter(pk=fridge.pk).exists()
        )
        assert not AuditLog.objects.exists()  # a refused removal leaves no trace

    def test_remove_an_unused_item_and_log_it(self, admin, make_hospital):
        hospital = make_hospital()
        dept = Department.objects.create(hospital=hospital, name="Surgery")
        ward = Ward.objects.create(code="w", name="W", kind="General", hospital=hospital, department=dept)
        assert admin.delete(structure_url(hospital, "departments", dept.pk)).status_code == 204
        ward.refresh_from_db()
        assert ward.department is None  # the ward stays, without a department
        entry = AuditLog.objects.get(action="department.deleted")
        assert entry.before == {"name": "Surgery", "hospital": hospital.pk}

    def test_items_are_found_only_under_their_own_hospital(self, admin, make_hospital):
        here, there = make_hospital("Here"), make_hospital("There")
        dept = Department.objects.create(hospital=there, name="Surgery")
        assert admin.delete(structure_url(here, "departments", dept.pk)).status_code == 404
        assert (
            admin.post(
                reverse("hospital-structure", kwargs={"pk": 999, "kind": "wards"}), {}, format="json"
            ).status_code
            == 404
        )
