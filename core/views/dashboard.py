from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from knowledge_base.models import KnowledgeQuery, Document
from field_operations.models import FieldInspection, InspectionAnalysis

from django.utils import timezone
from datetime import timedelta

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Real statistics
        context['total_inspections'] = FieldInspection.objects.count()
        context['emergency_alerts'] = InspectionAnalysis.objects.filter(is_emergency=True).count()
        context['knowledge_queries'] = KnowledgeQuery.objects.count()
        
        # Combine recent activities (Inspections and Knowledge Queries)
        recent_inspections = InspectionAnalysis.objects.select_related('inspection', 'inspection__inspector').order_by('-analysis_timestamp')[:5]
        recent_queries = KnowledgeQuery.objects.select_related('user').order_by('-timestamp')[:5]
        
        activities = []
        for i in recent_inspections:
            activities.append({
                'type': 'inspection',
                'title': f"{i.inspection.get_equipment_type_display()} Analyzed",
                'meta': f"Inspector: {i.inspection.inspector.username}",
                'timestamp': i.analysis_timestamp,
                'status': i.get_risk_classification_display(),
                'risk_class': i.risk_classification,
                'icon': 'fa-camera',
                'color': 'primary'
            })
            
        for q in recent_queries:
            activities.append({
                'type': 'query',
                'title': f"Knowledge Search: \"{q.query_text[:30]}...\"",
                'meta': f"By: {q.user.username}",
                'timestamp': q.timestamp,
                'status': 'Resolved',
                'risk_class': 'knowledge',
                'icon': 'fa-lightbulb',
                'color': 'success'
            })
            
        # Sort combined activity by time
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        context['activities'] = activities[:8]
        
        # Dynamic Orchestrator Status: Active if an inspection happened in the last 15 minutes
        recent_activity_threshold = timezone.now() - timedelta(minutes=15)
        is_active = InspectionAnalysis.objects.filter(analysis_timestamp__gt=recent_activity_threshold).exists()
        context['orchestrator_status'] = "Active" if is_active else "Idle"
        context['orchestrator_color'] = "var(--success)" if is_active else "var(--secondary)"
        
        profile = getattr(self.request.user, 'profile', None)
        context['user_role'] = profile.role if profile else 'unknown'
        return context

class KnowledgeQueryView(LoginRequiredMixin, TemplateView):
    template_name = 'core/knowledge_query.html'

class InspectionDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/inspection_dashboard.html'
