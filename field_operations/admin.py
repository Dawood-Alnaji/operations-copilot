from django.contrib import admin
from field_operations.models import FieldInspection, InspectionAnalysis, AgentReasoningLog

@admin.register(FieldInspection)
class FieldInspectionAdmin(admin.ModelAdmin):
    list_display = ['id', 'inspector', 'equipment_type', 'location', 'upload_timestamp', 'has_analysis']
    list_filter = ['equipment_type', 'upload_timestamp', 'analysis_requested']
    search_fields = ['inspector__username', 'location', 'notes']
    readonly_fields = ['upload_timestamp']
    
    def has_analysis(self, obj):
        return hasattr(obj, 'analysis')
    has_analysis.boolean = True
    has_analysis.short_description = 'Analyzed'

@admin.register(InspectionAnalysis)
class InspectionAnalysisAdmin(admin.ModelAdmin):
    list_display = ['inspection', 'risk_classification', 'is_emergency', 'analysis_timestamp', 'confidence_score']
    list_filter = ['risk_classification', 'is_emergency', 'analysis_timestamp']
    search_fields = ['technical_description', 'inspection__inspector__username']
    readonly_fields = ['analysis_timestamp', 'raw_llm_output']

@admin.register(AgentReasoningLog)
class AgentReasoningLogAdmin(admin.ModelAdmin):
    list_display = ['inspection_analysis', 'agent_name', 'processing_order', 'timestamp']
    list_filter = ['agent_name', 'timestamp']
    readonly_fields = ['timestamp', 'agent_output']
