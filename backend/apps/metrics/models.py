"""Hourly figures per hospital (B20), for the trend charts (B22). The seed fills two weeks of them; the
simulation (B21) keeps adding one row per figure per hour. The figures themselves are listed in catalog.py."""

from django.db import models


class MetricSnapshot(models.Model):
    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.CASCADE, related_name="+")
    metric = models.CharField(max_length=48, help_text='One of catalog.py, e.g. "er.arrivals".')
    at = models.DateTimeField(help_text="The start of the hour the figure covers (or was read at).")
    value = models.FloatField()

    class Meta:
        ordering = ["hospital", "metric", "at"]
        constraints = [
            models.UniqueConstraint(fields=["hospital", "metric", "at"], name="metrics_one_value_per_hour"),
        ]

    def __str__(self):
        return f"{self.hospital_id} {self.metric} @ {self.at:%d %b %H:%M} = {self.value:g}"
