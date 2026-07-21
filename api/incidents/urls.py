from django.urls import path
from .views import IncidentListView, HazardListView

urlpatterns = [
    path("incidents/", IncidentListView.as_view(), name="incident-list"),
    path("hazards/", HazardListView.as_view(), name="hazard-list"),
]