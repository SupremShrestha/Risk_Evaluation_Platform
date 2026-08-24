from rest_framework import serializers
from .models import Incident, Hazard, District, IncidentHotspot

class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = ["id", "title"]

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

class IncidentMapSerializer(serializers.ModelSerializer):
    hazard_title = serializers.CharField(source="hazard.title", default=None)
    hazard_color = serializers.CharField(source="hazard.color", default=None)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = ["id", "latitude", "longitude", "hazard_title", "hazard_color", "incident_on"]

    def get_latitude(self, obj):
        return obj.point.y if obj.point else None

    def get_longitude(self, obj):
        return obj.point.x if obj.point else None
    
class IncidentHotspotSerializer(serializers.ModelSerializer):
    hazard_title = serializers.CharField(source="hazard.title", read_only=True)
    hazard_color = serializers.CharField(source="hazard.color", default=None)
    dominant_district_title = serializers.CharField(source="dominant_district.title", default=None)

    class Meta:
        model = IncidentHotspot
        fields = [
            "id", "hazard_title", "hazard_color", "cluster_label", "size",
            "center_lat", "center_lon", "dominant_district_title",
        ]