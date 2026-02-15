from django.db import models
from django.contrib.auth.models import User


class AuditLog(models.Model):
    """Comprehensive audit trail for all sensitive operations"""
    
    ACTION_TYPE_CHOICES = [
        ('document_upload', 'Document Upload'),
        ('document_delete', 'Document Delete'),
        ('knowledge_query', 'Knowledge Query'),
        ('inspection_upload', 'Inspection Upload'),
        ('inspection_analysis', 'Inspection Analysis'),
        ('user_login', 'User Login'),
        ('user_logout', 'User Logout'),
        ('settings_change', 'Settings Change'),
        ('role_change', 'User Role Change'),
        ('emergency_alert', 'Emergency Alert'),
    ]
    
    RESOURCE_TYPE_CHOICES = [
        ('document', 'Document'),
        ('query', 'Knowledge Query'),
        ('inspection', 'Field Inspection'),
        ('user', 'User'),
        ('system', 'System'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='audit_logs',
        help_text="User who performed the action"
    )
    action_type = models.CharField(max_length=50, choices=ACTION_TYPE_CHOICES)
    resource_type = models.CharField(max_length=50, choices=RESOURCE_TYPE_CHOICES)
    resource_id = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="ID of the affected resource"
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_role_at_time = models.CharField(
        max_length=50, 
        help_text="User's role when action was performed"
    )
    request_payload = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Sanitized request data (no sensitive info)"
    )
    response_summary = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Summary of response/outcome"
    )
    success = models.BooleanField(default=True, help_text="Whether action succeeded")
    error_message = models.TextField(blank=True, help_text="Error details if failed")
    user_agent = models.CharField(
        max_length=255, 
        blank=True, 
        help_text="Browser/client user agent"
    )
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action_type', '-timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['success']),
        ]
    
    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        return f"{user_str} - {self.get_action_type_display()} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    @classmethod
    def log_action(cls, user, action_type, resource_type, resource_id=None, 
                   ip_address=None, request_payload=None, response_summary=None, 
                   success=True, error_message='', user_agent=''):
        """Helper method to create audit log entries"""
        user_role = 'unknown'
        if user and hasattr(user, 'profile'):
            user_role = user.profile.role
        
        return cls.objects.create(
            user=user,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_role_at_time=user_role,
            request_payload=request_payload or {},
            response_summary=response_summary or {},
            success=success,
            error_message=error_message,
            user_agent=user_agent
        )
