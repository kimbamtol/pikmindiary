from django.contrib import admin

from .models import NerfReport


@admin.register(NerfReport)
class NerfReportAdmin(admin.ModelAdmin):
    list_display = ['coordinate', 'reporter', 'created_at']
    list_filter = ['created_at']
    search_fields = ['coordinate__title', 'user__nickname', 'session_key']
    readonly_fields = ['coordinate', 'user', 'session_key', 'ip_address', 'created_at']
    ordering = ['-created_at']

    def reporter(self, obj):
        return obj.user.nickname if obj.user else f'비회원 ({obj.session_key[:8]})'
    reporter.short_description = '제보자'

    def has_add_permission(self, request):
        return False
