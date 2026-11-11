"""Story 5.1: distance and estimated travel time (#39)."""

import pytest

from apps.matching.distance import estimated_travel_minutes, haversine_km, hospital_distance


def test_same_point_is_zero_distance():
    assert haversine_km(24.8607, 67.0011, 24.8607, 67.0011) == 0


def test_one_degree_of_longitude_at_the_equator_is_about_111_km():
    # A well-known reference value: 1 degree of longitude at the equator is ~111.19 km.
    km = haversine_km(0, 0, 0, 1)
    assert 111.0 <= km <= 111.4


def test_distance_is_symmetric():
    a = haversine_km(24.8607, 67.0011, 31.5204, 74.3587)
    b = haversine_km(31.5204, 74.3587, 24.8607, 67.0011)
    assert a == pytest.approx(b)


@pytest.mark.parametrize(
    ("distance_km", "speed_kmh", "expected_minutes"),
    [
        (40.0, 40.0, 60.0),
        (0.0, 40.0, 0.0),
        (20.0, 60.0, 20.0),
    ],
)
def test_estimated_travel_minutes(distance_km, speed_kmh, expected_minutes):
    assert estimated_travel_minutes(distance_km, speed_kmh) == pytest.approx(expected_minutes)


def test_estimated_travel_minutes_defaults_to_40kmh():
    assert estimated_travel_minutes(40.0) == pytest.approx(60.0)


@pytest.mark.django_db
def test_hospital_distance_between_two_hospitals_at_the_same_coordinates_is_zero(make_hospital):
    a = make_hospital(name="Hospital A")
    b = make_hospital(name="Hospital B")
    assert hospital_distance(a, b) == 0


@pytest.mark.django_db
def test_hospital_distance_uses_each_hospitals_own_coordinates(make_hospital):
    karachi = make_hospital(name="Karachi General", latitude="24.8607", longitude="67.0011")
    lahore = make_hospital(name="Lahore General", latitude="31.5204", longitude="74.3587")
    expected = haversine_km(24.8607, 67.0011, 31.5204, 74.3587)
    assert hospital_distance(karachi, lahore) == pytest.approx(expected)
