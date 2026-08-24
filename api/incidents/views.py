from django.shortcuts import render
from rest_framework import generics
from .models import Incident, Hazard, District, DistrictDailyRainfall, IncidentHotspot
from .serializers import IncidentSerializer, HazardSerializer, DistrictSerializer, IncidentMapSerializer, IncidentHotspotSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .ml_service import get_model_and_encoders, compute_prediction_features, get_leadlag_model, get_leadlag_features
from datetime import datetime


class DistrictListView(generics.ListAPIView):
    queryset = District.objects.all().order_by("title")
    serializer_class = DistrictSerializer
    pagination_class = None  # only 77 districts total — no need to paginate

class IncidentListView(generics.ListAPIView):
    queryset = Incident.objects.select_related("hazard").order_by("-incident_on")
    serializer_class = IncidentSerializer
    
class HazardListView(generics.ListAPIView):
    queryset = Hazard.objects.all().order_by("title")
    serializer_class = HazardSerializer

class PredictRiskView(APIView):
    def post(self, request):
        district_name = request.data.get("district")
        hazard_title = request.data.get("hazard")
        year = request.data.get("year")
        month = request.data.get("month")

        if not all([district_name, hazard_title, year, month]):
            return Response(
                {"error": "district, hazard, year, and month are all required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            year, month = int(year), int(month)
        except ValueError:
            return Response(
                {"error": "year and month must be integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        model, encoders = get_model_and_encoders()

        # Encode district/hazard using the SAME encoders used during training
        try:
            district_encoded = encoders["district"].transform([district_name])[0]
            hazard_encoded = encoders["hazard"].transform([hazard_title])[0]
        except ValueError:
            return Response(
                {"error": f"Unknown district or hazard. Valid hazards: "
                          f"{list(encoders['hazard'].classes_)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prev_month_count, historical_month_avg = compute_prediction_features(
            district_name, hazard_title, year, month
        )

        import pandas as pd
        features = pd.DataFrame([{
            "district_encoded": district_encoded,
            "hazard_encoded": hazard_encoded,
            "month": month,
            "prev_month_count": prev_month_count,
            "historical_month_avg": historical_month_avg,
        }])

        prediction = model.predict(features)[0]
        prediction = max(0, round(float(prediction), 2))  # counts can't be negative

        return Response({
            "district": district_name,
            "hazard": hazard_title,
            "year": year,
            "month": month,
            "predicted_incident_count": prediction,
            "features_used": {
                "prev_month_count": prev_month_count,
                "historical_month_avg": round(historical_month_avg, 2),
            },
        })
        
class IncidentMapListView(generics.ListAPIView):
    queryset = Incident.objects.filter(point__isnull=False).select_related("hazard")
    serializer_class = IncidentMapSerializer
    pagination_class = None
    
class PredictHazardView(APIView):
    """
    Predicts hazard risk (probability of an incident occurring) for a
    district on a given date, using the lead-lag rainfall model.

    Unlike PredictRiskView (which predicts a monthly incident COUNT for a
    future month), this predicts a same/near-term-day binary risk
    PROBABILITY, driven by precomputed rainfall features. Deliberately a
    separate endpoint rather than folded into PredictRiskView -- different
    model type (classifier vs regressor), different feature set, different
    semantics of the output.
    """
    def post(self, request):
        district_name = request.data.get("district")
        date_str = request.data.get("date")

        if not all([district_name, date_str]):
            return Response(
                {"error": "district and date are both required (date as YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "date must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            district = District.objects.get(title=district_name)
        except District.DoesNotExist:
            return Response(
                {"error": f"Unknown district: {district_name}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        features = get_leadlag_features(district.id, target_date)
        if features is None:
            return Response(
                {"error": f"No rainfall data available for {district_name} on {date_str}. "
                          f"This means the daily ingestion DAG hasn't run for that date yet, "
                          f"or CHIRPS had a coverage gap for that window."},
                status=status.HTTP_404_NOT_FOUND,
            )

        model = get_leadlag_model()

        import pandas as pd
        feature_row = pd.DataFrame([{
            "rain_1d": features["rain_1d"],
            "rain_3d": features["rain_3d"],
            "rain_7d": features["rain_7d"],
            "rain_peak_7d": features["rain_peak_7d"],
            "month": features["month"],
            "district_id": features["district_id"],
        }])

        risk_probability = float(model.predict_proba(feature_row)[0][1])

        return Response({
            "district": district_name,
            "date": date_str,
            "risk_probability": round(risk_probability, 3),
            "features_used": {
                "rain_1d": round(features["rain_1d"], 2),
                "rain_3d": round(features["rain_3d"], 2),
                "rain_7d": round(features["rain_7d"], 2),
                "rain_peak_7d": round(features["rain_peak_7d"], 2),
            },
            "note": "This is a probability from a moderate-accuracy model "
                    "(time-based validation ROC-AUC 0.580) -- treat as a "
                    "risk-elevation signal, not a precise forecast.",
        })
        
class HotspotListView(generics.ListAPIView):
    queryset = IncidentHotspot.objects.select_related("hazard", "dominant_district").order_by("-size")
    serializer_class = IncidentHotspotSerializer
    pagination_class = None  # ~300 rows total across all hazards, no need to paginate