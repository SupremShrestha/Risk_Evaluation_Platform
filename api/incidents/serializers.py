from rest_framework import serializers
from .models import Incident, Hazard


class HazardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hazard
        fields = ["id", "title", "title_ne", "type", "color"]


class IncidentSerializer(serializers.ModelSerializer):
    hazard = HazardSerializer(read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = [
            "id", "title", "title_ne", "hazard",
            "incident_on", "reported_on", "verified", "approved",
            "latitude", "longitude",
        ]

    def get_latitude(self, obj):
        return obj.point.y if obj.point else None

    def get_longitude(self, obj):
        return obj.point.x if obj.point else None