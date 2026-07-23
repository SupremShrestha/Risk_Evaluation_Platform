from django.urls import path
from .views import IncidentListView, HazardListView
from django.urls import path
from .views import IncidentListView, HazardListView, PredictRiskView, DistrictListView, IncidentMapListView

urlpatterns = [
    path("incidents/", IncidentListView.as_view(), name="incident-list"),
    path("hazards/", HazardListView.as_view(), name="hazard-list"),
    path("districts/", DistrictListView.as_view(), name="district-list"),
    path("predict/", PredictRiskView.as_view(), name="predict-risk"),
    path("incidents/map/", IncidentMapListView.as_view(), name="incident-map"),
]