from django.shortcuts import render
from rest_framework import generics
from .models import Incident, Hazard
from .serializers import IncidentSerializer, HazardSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .ml_service import get_model_and_encoders, compute_prediction_features

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