from django.db import models
from django.contrib.gis.db import models


class Hazard(models.Model):
    id = models.IntegerField(primary_key=True)
    title = models.TextField()
    title_ne = models.TextField(null=True, blank=True)
    type = models.TextField(null=True, blank=True)
    color = models.TextField(null=True, blank=True)
    icon_url = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "hazards"

    def __str__(self):
        return self.title


class Incident(models.Model):
    id = models.IntegerField(primary_key=True)
    title = models.TextField(null=True, blank=True)
    title_ne = models.TextField(null=True, blank=True)
    hazard = models.ForeignKey(
        Hazard, on_delete=models.DO_NOTHING, db_column="hazard_id", null=True
    )
    incident_on = models.DateTimeField(null=True, blank=True)
    reported_on = models.DateTimeField(null=True, blank=True)
    verified = models.BooleanField(null=True)
    approved = models.BooleanField(null=True)
    source = models.TextField(null=True, blank=True)
    data_source = models.TextField(null=True, blank=True)
    point = models.PointField(srid=4326, null=True, blank=True)
    loss_id = models.IntegerField(null=True, blank=True)
    created_on = models.DateTimeField(null=True, blank=True)
    modified_on = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField()
    ingested_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "incidents"

    def __str__(self):
        return f"{self.title} ({self.incident_on})"