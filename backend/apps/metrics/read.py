"""Reading the hourly figures for the trend charts (B22): one or more figures over the last days, by hour or
by day, for the user's own hospital, or the whole network (or one hospital) for an admin without a hospital.

A figure named without its last part sums its family: `beds.occupied` is every bed type's
`beds.occupied.<type>`. By day, counts (arrivals, units issued...) add up and levels (occupied beds, the
wait...) average. Across the network, both add up over the hospitals, except the wait, which averages.
"""

from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from apps.core import clock

from . import catalog
from .models import MetricSnapshot

MAX_DAYS = 31
AVERAGED_ACROSS_HOSPITALS = {catalog.ER_WAIT_MINUTES}


def _matching(names: list[str]) -> dict[str, str]:
    """Stored metric name → the requested name it counts towards."""
    known = catalog.all_metrics()
    out = {}
    for name in names:
        for metric in known:
            if metric == name or metric.startswith(f"{name}."):
                out[metric] = name
    return out


def _family(name: str) -> str:
    return next((m for m in catalog.all_metrics() if m == name or m.startswith(f"{name}.")), name)


def is_count(name: str) -> bool:
    return _family(name) in catalog.COUNTS


def read(names: list[str], *, hospitals, days: int, bucket: str, typical: bool, per_hospital: bool = False):
    """{"series": {name: [{"at", "value"}]}, "typical": {name: [{"hour", "value"}]}, "from", "to"}. With
    `per_hospital`, series are keyed "name@<hospital id>" instead."""
    now = clock.now()
    end = timezone.localtime(now).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days) + timedelta(hours=1)
    wanted = _matching(names)
    rows = MetricSnapshot.objects.filter(metric__in=wanted, at__gte=start, at__lte=end)
    if hospitals is not None:
        rows = rows.filter(hospital__in=hospitals)
    # (requested name, hospital, hour) → value, families summed within a hospital
    hourly: dict[tuple, float] = defaultdict(float)
    for metric, hospital_id, at, value in rows.values_list("metric", "hospital_id", "at", "value"):
        hourly[(wanted[metric], hospital_id, at)] += value

    def key(name, hospital_id):
        return f"{name}@{hospital_id}" if per_hospital else name

    # Across hospitals, by hour.
    combined: dict[tuple, list[float]] = defaultdict(list)
    for (name, hospital_id, at), value in hourly.items():
        combined[(key(name, hospital_id), name, at)].append(value)
    by_hour: dict[str, dict] = defaultdict(dict)
    for (series_key, name, at), values in combined.items():
        total = sum(values) / len(values) if _family(name) in AVERAGED_ACROSS_HOSPITALS else sum(values)
        by_hour[series_key][at] = total

    series = {}
    for series_key, points in by_hour.items():
        name = series_key.split("@")[0]
        if bucket == "day":
            days_of: dict = defaultdict(list)
            for at, value in points.items():
                days_of[timezone.localtime(at).date()].append(value)
            series[series_key] = [
                {"at": day.isoformat(), "value": round(sum(v) if is_count(name) else sum(v) / len(v), 2)}
                for day, v in sorted(days_of.items())
            ]
        else:
            series[series_key] = [{"at": at, "value": round(v, 2)} for at, v in sorted(points.items())]
    for name in names:
        if not per_hospital:
            series.setdefault(name, [])

    result = {"from": start, "to": end, "bucket": bucket, "series": series, "updatedAt": now}
    if typical:
        result["typical"] = typical_day(names, hospitals=hospitals, now=now)
    return result


def typical_day(names: list[str], *, hospitals, now) -> dict:
    """Each figure's average by hour of the day over the last 14 days: the band "today" is drawn against."""
    wanted = _matching(names)
    start = now - timedelta(days=14)
    rows = MetricSnapshot.objects.filter(metric__in=wanted, at__gte=start, at__lt=now - timedelta(hours=1))
    if hospitals is not None:
        rows = rows.filter(hospital__in=hospitals)
    per_hour: dict[tuple, float] = defaultdict(float)
    for metric, at, value in rows.values_list("metric", "at", "value"):
        per_hour[(wanted[metric], at)] += value  # summed over hospitals and family members
    by_clock: dict[tuple, list[float]] = defaultdict(list)
    for (name, at), value in per_hour.items():
        by_clock[(name, timezone.localtime(at).hour)].append(value)
    out = {}
    for name in names:
        out[name] = [
            {"hour": hour, "value": round(sum(v) / len(v), 2)}
            for hour in range(24)
            if (v := by_clock.get((name, hour)))
        ]
    return out
