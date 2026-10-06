from django.db import models


class Medicine(models.Model):
    code = models.SlugField(max_length=50, unique=True, help_text="Stable id used by the frontend.")
    name = models.CharField(max_length=150, help_text="Generic name.")
    strength = models.CharField(max_length=60)
    form = models.CharField(max_length=60)
    category = models.CharField(max_length=60)
    unit = models.CharField(max_length=30, help_text='Counting unit, e.g. "tablets", "vials".')
    reorder_level = models.PositiveIntegerField()
    daily_use = models.DecimalField(
        max_digits=8, decimal_places=1, help_text="Average units used per day over the last 30 days."
    )
    location = models.CharField(max_length=100)
    high_alert = models.BooleanField(default=False, help_text="On the ISMP list of high-alert medications.")
    controlled = models.BooleanField(default=False, help_text="Controlled drug: kept in the CD cabinet.")

    class Meta:
        ordering = ["name", "strength"]

    def __str__(self):
        return f"{self.name} {self.strength}"


class Batch(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="batches")
    number = models.CharField(max_length=40)
    expires_on = models.DateField()
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ["expires_on"]
        verbose_name_plural = "batches"
        constraints = [
            models.UniqueConstraint(fields=["medicine", "number"], name="pharmacy_batch_unique_per_medicine")
        ]

    def __str__(self):
        return f"{self.medicine} batch {self.number}"
