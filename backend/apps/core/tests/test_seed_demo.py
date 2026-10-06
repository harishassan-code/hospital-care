import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.blood.models import BloodUnit
from apps.hospitals.models import Bed
from apps.pharmacy.models import Medicine

pytestmark = pytest.mark.django_db


def test_seed_demo_is_repeatable():
    call_command("seed_demo", stdout=None)
    counts = (Bed.objects.count(), BloodUnit.objects.count(), Medicine.objects.count(), User.objects.count())
    call_command("seed_demo", stdout=None)
    assert counts == (106, 320, 23, 6)
    assert (
        Bed.objects.count(),
        BloodUnit.objects.count(),
        Medicine.objects.count(),
        User.objects.count(),
    ) == counts
