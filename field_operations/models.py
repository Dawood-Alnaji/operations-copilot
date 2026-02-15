from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator


class FieldInspection(models.Model):
    """Field images uploaded for equipment inspection and analysis"""
    
    EQUIPMENT_TYPE_CHOICES = [
        ('transformer', 'Transformer'),
        ('cable', 'Power Cable'),
        ('meter', 'Electricity Meter'),
        ('pole', 'Utility Pole'),
        ('switchgear', 'Switchgear'),
        ('substation', 'Substation Equipment'),
        ('other', 'Other Equipment'),
    ]
    
    inspector = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inspections')
    image = models.ImageField(
        upload_to='inspections/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])]
    )
    location = models.CharField(
        max_length=255, 
        blank=True, 
        help_text="GPS coordinates or location description"
    )
    equipment_type = models.CharField(max_length=50, choices=EQUIPMENT_TYPE_CHOICES)
    upload_timestamp = models.DateTimeField(auto_now_add=True)
    analysis_requested = models.BooleanField(default=True)
    notes = models.TextField(blank=True, help_text="Inspector's notes")
    
    class Meta:
        ordering = ['-upload_timestamp']
        indexes = [
            models.Index(fields=['-upload_timestamp']),
            models.Index(fields=['inspector', '-upload_timestamp']),
            models.Index(fields=['equipment_type']),
        ]
    
    def __str__(self):
        return f"{self.equipment_type} inspection by {self.inspector.username} on {self.upload_timestamp.strftime('%Y-%m-%d')}"


class InspectionAnalysis(models.Model):
    """Vision LLM analysis results for field inspections"""
    
    RISK_CLASSIFICATION_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    inspection = models.OneToOneField(
        FieldInspection, 
        on_delete=models.CASCADE, 
        related_name='analysis'
    )
    technical_description = models.TextField(help_text="Technical assessment from vision LLM")
    risk_classification = models.CharField(max_length=20, choices=RISK_CLASSIFICATION_CHOICES)
    safety_warnings = models.TextField(help_text="Identified safety hazards")
    recommended_actions = models.TextField(help_text="Recommended next steps")
    inspection_checklist = models.JSONField(
        default=dict, 
        help_text="Structured checklist results (visual_damage, overheating, etc.)"
    )
    is_emergency = models.BooleanField(
        default=False, 
        help_text="Critical emergency condition detected"
    )
    analysis_timestamp = models.DateTimeField(auto_now_add=True)
    analyzed_by_agent = models.CharField(
        max_length=100, 
        default='vision_llm', 
        help_text="Which agent/model performed analysis"
    )
    confidence_score = models.FloatField(
        null=True, 
        blank=True, 
        help_text="Analysis confidence (0.0-1.0)"
    )
    raw_llm_output = models.JSONField(
        null=True, 
        blank=True, 
        help_text="Raw structured output from LLM"
    )
    
    class Meta:
        ordering = ['-analysis_timestamp']
        indexes = [
            models.Index(fields=['risk_classification']),
            models.Index(fields=['is_emergency']),
            models.Index(fields=['-analysis_timestamp']),
        ]
    
    def __str__(self):
        return f"Analysis: {self.risk_classification} risk - {self.inspection}"


class AgentReasoningLog(models.Model):
    """Multi-agent reasoning chain logs for complex analysis"""
    
    AGENT_NAMES = [
        ('technical_ops', 'Technical Operations Agent'),
        ('safety', 'Safety Compliance Agent'),
        ('risk', 'Risk Assessment Agent'),
        ('executive', 'Executive Summary Agent'),
    ]
    
    inspection_analysis = models.ForeignKey(
        InspectionAnalysis, 
        on_delete=models.CASCADE, 
        related_name='agent_logs'
    )
    agent_name = models.CharField(max_length=50, choices=AGENT_NAMES)
    agent_role = models.TextField(help_text="Agent role description")
    agent_output = models.JSONField(help_text="Structured agent reasoning and conclusions")
    processing_order = models.IntegerField(help_text="Sequential execution order (1, 2, 3...)")
    timestamp = models.DateTimeField(auto_now_add=True)
    execution_time_ms = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Agent execution time in milliseconds"
    )
    
    class Meta:
        ordering = ['inspection_analysis', 'processing_order']
        indexes = [
            models.Index(fields=['inspection_analysis', 'processing_order']),
            models.Index(fields=['agent_name']),
        ]
        unique_together = [['inspection_analysis', 'processing_order']]
    
    def __str__(self):
        return f"{self.get_agent_name_display()} - Order {self.processing_order}"
