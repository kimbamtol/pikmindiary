from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UserBan


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['nickname', 'username', 'email', 'special_title', 'total_posts', 'is_staff']
    list_filter = ['special_title', 'is_staff', 'is_active']
    search_fields = ['nickname', 'username', 'email']
    list_editable = ['special_title']
    ordering = ['-date_joined']

    fieldsets = UserAdmin.fieldsets + (
        ('프로필 정보', {
            'fields': ('nickname', 'bio', 'profile_image', 'profile_emoji', 'special_title')
        }),
        ('통계', {
            'fields': ('total_posts', 'total_likes_received'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('프로필 정보', {
            'fields': ('nickname', 'special_title')
        }),
    )


@admin.register(UserBan)
class UserBanAdmin(admin.ModelAdmin):
    list_display = ['user', 'ip_address', 'duration', 'reason', 'banned_at', 'is_active']
    list_filter = ['duration', 'is_active']
    search_fields = ['user__nickname', 'ip_address', 'reason']
    ordering = ['-banned_at']
