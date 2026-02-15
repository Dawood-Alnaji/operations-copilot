from rest_framework import serializers
from field_operations.models import FieldInspection, InspectionAnalysis, AgentReasoningLog


class FieldInspectionSerializer(serializers.ModelSerializer):
    """Serializer for field inspection uploads"""
    
    inspector_name = serializers.CharField(source='inspector.get_full_name', read_only=True)
    equipment_type_display = serializers.CharField(source='get_equipment_type_display', read_only=True)
    has_analysis = serializers.SerializerMethodField()
    
    class Meta:
        model = FieldInspection
        fields = [
            'id', 'inspector', 'inspector_name', 'image', 'location',
            'equipment_type', 'equipment_type_display', 'upload_timestamp',
            'analysis_requested', 'notes', 'has_analysis'
        ]
        read_only_fields = ['id', 'inspector', 'upload_timestamp']
    
    def get_has_analysis(self, obj):
        return hasattr(obj, 'analysis')


class InspectionUploadSerializer(serializers.Serializer):
    """Serializer for inspection image upload"""
    
    image = serializers.ImageField()
    equipment_type = serializers.ChoiceField(choices=FieldInspection.EQUIPMENT_TYPE_CHOICES)
    location = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    analyze_immediately = serializers.BooleanField(default=True)


class InspectionChecklistSerializer(serializers.Serializer):
    """Serializer for inspection checklist items"""
    
    # Dynamic fields based on equipment type
    def to_representation(self, instance):
        return instance


class InspectionAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for inspection analysis results"""
    
    inspection_details = FieldInspectionSerializer(source='inspection', read_only=True)
    risk_classification_display = serializers.CharField(source='get_risk_classification_display', read_only=True)
    safety_warnings_list = serializers.SerializerMethodField()
    recommended_actions_list = serializers.SerializerMethodField()
    
    class Meta:
        model = InspectionAnalysis
        fields = [
            'id', 'inspection', 'inspection_details', 'technical_description',
            'risk_classification', 'risk_classification_display',
            'safety_warnings', 'safety_warnings_list',
            'recommended_actions', 'recommended_actions_list',
            'inspection_checklist', 'is_emergency', 'analysis_timestamp',
            'analyzed_by_agent', 'confidence_score'
        ]
        read_only_fields = ['id', 'analysis_timestamp']
    
    def get_safety_warnings_list(self, obj):
        if obj.safety_warnings:
            return [w.strip() for w in obj.safety_warnings.split('\n') if w.strip()]
        return []
    
    def get_recommended_actions_list(self, obj):
        if obj.recommended_actions:
            return [a.strip() for a in obj.recommended_actions.split('\n') if a.strip()]
        return []


class AgentReasoningLogSerializer(serializers.ModelSerializer):
    """Serializer for multi-agent reasoning logs"""
    
    agent_name_display = serializers.CharField(source='get_agent_name_display', read_only=True)
    
    class Meta:
        model = AgentReasoningLog
        fields = [
            'id', 'agent_name', 'agent_name_display', 'agent_role',
            'agent_output', 'processing_order', 'timestamp', 'execution_time_ms'
        ]
        read_only_fields = ['id', 'timestamp']


class InspectionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with analysis and agent logs"""
    
    inspection_details = FieldInspectionSerializer(source='inspection', read_only=True)
    agent_logs = AgentReasoningLogSerializer(many=True, read_only=True)
    risk_classification_display = serializers.CharField(source='get_risk_classification_display', read_only=True)
    
    class Meta:
        model = InspectionAnalysis
        fields = [
            'id', 'inspection_details', 'technical_description',
            'risk_classification', 'risk_classification_display',
            'safety_warnings', 'recommended_actions',
            'inspection_checklist', 'is_emergency', 'analysis_timestamp',
            'confidence_score', 'agent_logs'
        ]
        read_only_fields = ['id', 'analysis_timestamp']
