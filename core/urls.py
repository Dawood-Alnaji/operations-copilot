from django.urls import path
from .views.dashboard import DashboardView, KnowledgeQueryView, InspectionDashboardView

app_name = 'core'

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('assistant/', KnowledgeQueryView.as_view(), name='knowledge_query'),
    path('inspections/', InspectionDashboardView.as_view(), name='inspection_dashboard'),
]
