from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from core.models import UserProfile

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ['role', 'department', 'employee_id', 'phone_number']

# Re-register UserAdmin with Profile
admin.site.unregister(User)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'profile__role']
    
    def get_role(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.get_role_display()
        return 'No Profile'
    get_role.short_description = 'Role'
    get_role.admin_order_field = 'profile__role'

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'department', 'employee_id', 'phone_number']
    list_filter = ['role', 'department']
    search_fields = ['user__username', 'user__email', 'employee_id', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']
