"""B13 search performance (spec acceptance): the candidate search makes the same number of database queries on
a network of 10 hospitals as on one of 3, so a city-sized network adds no queries per hospital. The one-second
budget lives in test_candidates_performance.py, which is not edited. This file checks that the count holds.
"""

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

QUERY_BUDGET = 10  # the same budget as test_candidates_performance.py


def search_queries(case):
    """The queries one candidate search makes, serialised as the API serialises it."""
    with CaptureQueriesContext(connection) as captured:
        found = candidates_for_case(case)
        items = CandidateItemSerializer(found, many=True).data
        hospitals = HospitalMatchSerializer(match_hospitals(found), many=True).data
    assert items and hospitals, "the search should find candidates, or the count proves nothing"
    return len(captured.captured_queries)


def candidate_rows(case):
    return sum(len(item.candidates) for item in candidates_for_case(case))


def test_the_search_makes_the_same_queries_at_ten_hospitals_as_at_three():
    call_command("seed_demo", "--hospitals", "3", stdout=StringIO())
    origin = Hospital.objects.get(name="Seaview Hospital")
    case = EmergencyRequest.objects.create(reference="EC-2026-9003", severity="critical", hospital=origin)
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

    at_three = search_queries(case)
    rows_at_three = candidate_rows(case)

    call_command("seed_demo", "--hospitals", "10", stdout=StringIO())
    at_ten = search_queries(case)
    rows_at_ten = candidate_rows(case)

    assert rows_at_ten > rows_at_three, "the bigger network should offer more candidates"
    assert at_ten <= QUERY_BUDGET
    assert at_ten == at_three
