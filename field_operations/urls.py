from django.urls import path
from field_operations.views import (
    InspectionUploadView, InspectionListView, InspectionDetailView,
    AnalyticsRiskSummaryView, EmergencyAlertsView
)

app_name = 'field_operations'

urlpatterns = [
    # Inspections
    path('inspections/upload/', InspectionUploadView.as_view(), name='inspection-upload'),
    path('inspections/', InspectionListView.as_view(), name='inspection-list'),
    path('inspections/<int:inspection_id>/', InspectionDetailView.as_view(), name='inspection-detail'),
    
    # Analytics (Manager/Admin only)
    path('analytics/risk-summary/', AnalyticsRiskSummaryView.as_view(), name='analytics-risk'),
    path('analytics/emergency-alerts/', EmergencyAlertsView.as_view(), name='analytics-emergency'),
]
