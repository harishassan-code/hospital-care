"""GET /api/metrics/ (B22): the hourly figures behind the trend charts."""

from django.http import Http404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import module_permission
from apps.hospitals.models import Hospital

from . import catalog
from .read import MAX_DAYS, read


class MetricsQuery(serializers.Serializer):
    metrics = serializers.CharField(help_text="Comma-separated, e.g. er.arrivals,beds.occupied")
    days = serializers.IntegerField(min_value=1, max_value=MAX_DAYS, default=1)
    bucket = serializers.ChoiceField(choices=["hour", "day"], default="hour")
    typical = serializers.BooleanField(default=False)
    hospital = serializers.IntegerField(required=False)
    perHospital = serializers.BooleanField(default=False)

    def validate_metrics(self, value):
        names = [n.strip() for n in value.split(",") if n.strip()]
        known = catalog.all_metrics()
        unknown = [n for n in names if not any(m == n or m.startswith(f"{n}.") for m in known)]
        if not names or unknown or len(names) > 12:
            raise serializers.ValidationError(f"Unknown or too many figures: {', '.join(unknown) or value}.")
        return names


class MetricsView(APIView):
    """Staff read their own hospital's figures. An admin without a hospital reads the whole network, one
    hospital (`hospital=`), or every hospital apart (`perHospital=true`). Someone else's hospital is a 404."""

    permission_classes = [module_permission("metrics")]

    def get(self, request):
        query = MetricsQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        q = query.validated_data
        user = request.user
        network = user.hospital_id is None and user.effective_role == Role.ADMIN
        if user.hospital_id:
            if q.get("hospital") not in (None, user.hospital_id):
                raise Http404("No hospital with that id.")
            hospitals = Hospital.objects.filter(pk=user.hospital_id)
        elif network:
            hospitals = None if q.get("hospital") is None else Hospital.objects.filter(pk=q["hospital"])
            if hospitals is not None and not hospitals.exists():
                raise Http404("No hospital with that id.")
        else:
            raise Http404("You aren't attached to a hospital.")
        body = read(
            q["metrics"],
            hospitals=hospitals,
            days=q["days"],
            bucket=q["bucket"],
            typical=q["typical"],
            per_hospital=q["perHospital"] and network and hospitals is None,
        )
        return Response(body)
