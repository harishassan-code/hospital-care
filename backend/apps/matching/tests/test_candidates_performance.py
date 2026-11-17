"""Story #38 acceptance: the search over the seeded demo network returns in under a second, in a fixed number
of queries. Seeded data, as a demo sees it: a case at the second hospital, one need of each of the four types.
Story #41 adds the ranking and the serialising of the scores to the same budget: scoring is pure Python.
Story #42 adds the hospitals judged across the needs, and their serialising, with no query of their own.
"""

import time
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.emergencies.models import EmergencyRequest, RequestItem
from apps.emergencies.serializers import CandidateItemSerializer, HospitalMatchSerializer
from apps.hospitals.models import Hospital
from apps.matching.candidates import candidates_for_case
from apps.matching.multi import match_hospitals

pytestmark = pytest.mark.django_db

SECONDS = 1.0
QUERY_BUDGET = 10  # the case's items, four stock counts, one grouped search per item, one hospital fetch


def test_candidates_for_one_need_of_each_type_on_seeded_data_are_fast_and_bounded(
    django_assert_max_num_queries,
):
    call_command("seed_demo", stdout=StringIO())
    origin = Hospital.objects.get(name="Seaview Hospital")
    case = EmergencyRequest.objects.create(reference="EC-2026-9001", severity="critical", hospital=origin)
    RequestItem.objects.bulk_create(
        [
            RequestItem(
                request=case, resource_type="blood", blood_group="A+", component="redCells", quantity=50
            ),
            RequestItem(request=case, resource_type="bed", bed_type="general", quantity=50),
            RequestItem(request=case, resource_type="equipment", equipment_type="ventilator", quantity=50),
            RequestItem(request=case, resource_type="operatingRoom", capability="general", quantity=50),
        ]
    )
    case = EmergencyRequest.objects.select_related("hospital").get(pk=case.pk)

    started = time.perf_counter()
    with django_assert_max_num_queries(QUERY_BUDGET):
        found = candidates_for_case(case)
        payload = CandidateItemSerializer(found, many=True).data
        hospitals = HospitalMatchSerializer(match_hospitals(found), many=True).data
    elapsed = time.perf_counter() - started

    assert elapsed < SECONDS, f"candidates_for_case took {elapsed:.3f}s"
    assert [entry.item.resource_type for entry in found] == ["blood", "bed", "equipment", "operatingRoom"]
    assert all(entry.candidates for entry in found), "every type should find a hospital with stock"
    assert all(item["candidates"][0]["rank"] == 1 for item in payload)
    assert hospitals and hospitals[0]["rank"] == 1


def test_the_hospitals_judged_across_the_needs_cost_no_query():
    """Story #42: the same search with and without the hospitals makes the same number of queries."""
    call_command("seed_demo", stdout=StringIO())
    origin = Hospital.objects.get(name="Seaview Hospital")
    case = EmergencyRequest.objects.create(reference="EC-2026-9002", severity="critical", hospital=origin)
    RequestItem.objects.bulk_create(
        [
            RequestItem(
                request=case, resource_type="blood", blood_group="A+", component="redCells", quantity=50
            ),
            RequestItem(request=case, resource_type="bed", bed_type="general", quantity=50),
        ]
    )
    case = EmergencyRequest.objects.select_related("hospital").get(pk=case.pk)

    def items_only():
        return CandidateItemSerializer(candidates_for_case(case), many=True).data

    def with_hospitals():
        found = candidates_for_case(case)
        return CandidateItemSerializer(found, many=True).data, HospitalMatchSerializer(
            match_hospitals(found), many=True
        ).data

    with CaptureQueriesContext(connection) as before:
        items_only()
    with CaptureQueriesContext(connection) as after:
        _, hospitals = with_hospitals()

    assert hospitals, "the seeded network should have a hospital for these needs"
    assert len(after.captured_queries) == len(before.captured_queries)
