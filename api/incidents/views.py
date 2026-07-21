from django.shortcuts import render
from rest_framework import generics
from .models import Incident
from .serializers import IncidentSerializer


class IncidentListView(generics.ListAPIView):
    queryset = Incident.objects.select_related("hazard").order_by("-incident_on")
    serializer_class = IncidentSerializer