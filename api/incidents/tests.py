from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .models import Incident, Hazard, District
from django.contrib.gis.geos import Point


class HazardEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Hazard.objects.create(id=17, title="Landslide", type="natural", color="#6D4C41")
        Hazard.objects.create(id=20, title="Snake Bite", type="non natural", color="#AB47BC")

    def test_hazards_list_returns_all_hazards(self):
        response = self.client.get("/api/v1/hazards/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_hazards_are_ordered_by_title(self):
        response = self.client.get("/api/v1/hazards/")
        titles = [h["title"] for h in response.data["results"]]
        self.assertEqual(titles, sorted(titles))


class IncidentEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hazard = Hazard.objects.create(id=17, title="Landslide", type="natural")
        self.district = District.objects.create(id=39, title="Rolpa")
        Incident.objects.create(
            id=1,
            title="Landslide at Test Village",
            hazard=self.hazard,
            district=self.district,
            incident_on="2026-07-15T00:00:00Z",
            verified=True,
            point=Point(82.6, 28.3, srid=4326),
            raw_data={},
        )

    def test_incidents_list_returns_incident(self):
        response = self.client.get("/api/v1/incidents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_incident_includes_nested_hazard(self):
        response = self.client.get("/api/v1/incidents/")
        incident = response.data["results"][0]
        self.assertEqual(incident["hazard"]["title"], "Landslide")

    def test_incident_extracts_lat_lng_from_point(self):
        response = self.client.get("/api/v1/incidents/")
        incident = response.data["results"][0]
        self.assertAlmostEqual(incident["latitude"], 28.3, places=1)
        self.assertAlmostEqual(incident["longitude"], 82.6, places=1)

    def test_pagination_is_active(self):
        response = self.client.get("/api/v1/incidents/")
        self.assertIn("next", response.data)
        self.assertIn("count", response.data)