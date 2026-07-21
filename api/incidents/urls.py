from django.urls import path
from .views import IncidentListView, HazardListView
from django.urls import path
from .views import IncidentListView, HazardListView, PredictRiskView

urlpatterns = [
    path("incidents/", IncidentListView.as_view(), name="incident-list"),
    path("hazards/", HazardListView.as_view(), name="hazard-list"),
    path("predict/", PredictRiskView.as_view(), name="predict-risk"),
]