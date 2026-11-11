"""Story 5.1: distance and estimated travel time between hospitals (#39).

Straight-line (Haversine) distance from coordinates, and a simulated travel-time estimate from an
average city driving speed. No real routing or traffic data — see docs/aidlc/inception for scope.
"""

import math
from decimal import Decimal

EARTH_RADIUS_KM = 6371.0
DEFAULT_AVERAGE_SPEED_KMH = 40.0


def haversine_km(
    lat1: Decimal | float, lon1: Decimal | float, lat2: Decimal | float, lon2: Decimal | float
) -> float:
    """Straight-line distance in kilometres between two lat/long points."""
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    d_phi = math.radians(float(lat2) - float(lat1))
    d_lambda = math.radians(float(lon2) - float(lon1))

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimated_travel_minutes(
    distance_km: float, average_speed_kmh: float = DEFAULT_AVERAGE_SPEED_KMH
) -> float:
    """Simulated travel time in minutes: distance over an assumed average city driving speed."""
    return (distance_km / average_speed_kmh) * 60


def hospital_distance(hospital_a, hospital_b) -> float:
    """Straight-line distance in kilometres between two Hospital instances."""
    return haversine_km(hospital_a.latitude, hospital_a.longitude, hospital_b.latitude, hospital_b.longitude)
