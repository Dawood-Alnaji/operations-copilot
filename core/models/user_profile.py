from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """Extended user profile with role-based access control for electricity company staff"""
    
    ROLE_CHOICES = [
        ('field_engineer', 'Field Engineer'),
        ('ops_manager', 'Operations Manager'),
        ('admin', 'Administrator'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='field_engineer')
    department = models.CharField(max_length=100, blank=True, help_text="Department name")
    employee_id = models.CharField(max_length=50, unique=True, help_text="Employee ID number")
    phone_number = models.CharField(max_length=20, blank=True, help_text="Contact phone number")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['employee_id']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_role_display()}"
    
    def is_field_engineer(self):
        return self.role == 'field_engineer'
    
    def is_operations_manager(self):
        return self.role == 'ops_manager'
    
    def is_admin(self):
        return self.role == 'admin'
    
    def has_document_upload_permission(self):
        """Only admins can upload documents to knowledge base"""
        return self.is_admin()
    
    def has_analytics_access(self):
        """Managers and admins can view analytics"""
        return self.role in ['ops_manager', 'admin']
    
    def has_audit_log_access(self):
        """Managers and admins can view audit logs"""
        return self.role in ['ops_manager', 'admin']


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create UserProfile when a new User is created"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()
