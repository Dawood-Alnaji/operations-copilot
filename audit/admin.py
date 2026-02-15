from django.contrib import admin
from audit.models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action_type', 'resource_type', 'timestamp', 'success', 'ip_address']
    list_filter = ['action_type', 'resource_type', 'success', 'timestamp']
    search_fields = ['user__username', 'error_message', 'ip_address']
    readonly_fields = ['timestamp', 'user', 'action_type', 'resource_type', 'resource_id',
                       'ip_address', 'user_role_at_time', 'request_payload', 'response_summary',
                       'success', 'error_message', 'user_agent']
    
    def has_add_permission(self, request):
        # Audit logs should not be manually created
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Audit logs should not be deleted (except by superuser)
        return request.user.is_superuser
