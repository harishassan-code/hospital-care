"""Story #55: the query count is fixed on the seeded demo network, and does not grow with more hospitals."""

import time
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import Role
from apps.command_centre.services import network_figures

from .support import stocked_hospital

pytestmark = pytest.mark.django_db

BUDGET = 15  # the acceptance criterion; the service makes 7 grouped queries, the sweeps 2 more
URL = reverse("command-centre")


def queries_of(call) -> int:
    with CaptureQueriesContext(connection) as captured:
        call()
    return len(captured.captured_queries)


def test_the_service_stays_within_budget_on_the_seeded_network(django_assert_max_num_queries):
    call_command("seed_demo", stdout=StringIO())
    with django_assert_max_num_queries(BUDGET):
        network_figures()


def test_the_endpoint_with_its_sweeps_stays_within_budget(client_as, django_assert_max_num_queries):
    call_command("seed_demo", stdout=StringIO())
    client = client_as(Role.ADMIN)
    with django_assert_max_num_queries(BUDGET):
        response = client.get(URL)
    assert response.status_code == 200


def test_adding_two_active_hospitals_with_stock_and_cases_changes_nothing_in_the_count(
    make_user, make_hospital
):
    call_command("seed_demo", stdout=StringIO())
    before = queries_of(network_figures)
    assert before <= BUDGET
    for name in ("Northwest Clinic", "Eastfield Hospital"):
        stocked_hospital(make_hospital(name), make_user)
    assert queries_of(network_figures) == before


def test_the_seeded_network_answers_in_under_a_second(client_as):
    call_command("seed_demo", stdout=StringIO())
    client = client_as(Role.ADMIN)
    started = time.perf_counter()
    response = client.get(URL)
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert elapsed < 1.0, f"command centre took {elapsed:.3f}s"
