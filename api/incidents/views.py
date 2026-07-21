from django.shortcuts import render
from rest_framework import generics
from .models import Incident, Hazard
from .serializers import IncidentSerializer, HazardSerializer

class IncidentListView(generics.ListAPIView):
    queryset = Incident.objects.select_related("hazard").order_by("-incident_on")
    serializer_class = IncidentSerializer
    
class HazardListView(generics.ListAPIView):
    queryset = Hazard.objects.all().order_by("title")
    serializer_class = HazardSerializer