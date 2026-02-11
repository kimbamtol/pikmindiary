from django.contrib import admin
from .models import SiteNotice, Suggestion, SiteSettings


@admin.register(SiteNotice)
class SiteNoticeAdmin(admin.ModelAdmin):
    list_display = ['location', 'title', 'is_active', 'updated_at']
    list_filter = ['location', 'is_active']
    list_editable = ['is_active']
    search_fields = ['title', 'content']


@admin.register(Suggestion)
class SuggestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'category', 'title', 'content_preview', 'writer_name', 'status', 'created_at']
    list_filter = ['status', 'category', 'created_at']
    list_editable = ['status']
    list_display_links = ['id', 'title']
    search_fields = ['title', 'content', 'guest_nickname', 'email']
    readonly_fields = ['author', 'guest_nickname', 'email', 'category', 'title', 'content', 'created_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('작성자 정보', {
            'fields': ('author', 'guest_nickname', 'email')
        }),
        ('건의 내용', {
            'fields': ('category', 'title', 'content', 'created_at')
        }),
        ('관리', {
            'fields': ('status', 'admin_reply', 'admin_note')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        from apps.interactions.models import Notification
        
        # 기존 상태 확인 (수정인 경우)
        old_status = None
        old_reply = None
        if change and obj.pk:
            try:
                old_obj = Suggestion.objects.get(pk=obj.pk)
                old_status = old_obj.status
                old_reply = old_obj.admin_reply
            except Suggestion.DoesNotExist:
                pass
        
        # 답변이 추가되면 replied_at 자동 설정
        if obj.admin_reply and not obj.replied_at:
            obj.replied_at = timezone.now()
        
        super().save_model(request, obj, form, change)
        
        # 회원인 경우에만 알림 전송
        if obj.author:
            # 답변이 새로 추가된 경우
            if obj.admin_reply and (not old_reply or old_reply != obj.admin_reply):
                Notification.objects.create(
                    recipient=obj.author,
                    actor=None,
                    notification_type=Notification.NotificationType.SUGGESTION_REPLY,
                    coordinate=None,
                    message=f"📋 건의사항 '{obj.title}'에 운영자가 답변했습니다!"
                )
            # 상태가 변경된 경우 (답변 알림과 중복 방지)
            elif old_status and old_status != obj.status:
                status_label = obj.get_status_display()
                Notification.objects.create(
                    recipient=obj.author,
                    actor=None,
                    notification_type=Notification.NotificationType.SUGGESTION_REPLY,
                    coordinate=None,
                    message=f"📋 건의사항 '{obj.title}'이(가) '{status_label}'(으)로 변경되었습니다."
                )
    
    def writer_name(self, obj):
        return obj.writer_name
    writer_name.short_description = '작성자'
    
    def content_preview(self, obj):
        """내용 미리보기 (50자)"""
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    content_preview.short_description = '내용'


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'ranker_limit_exempt_rank', 'daily_upload_limit', 'updated_at']
    
    fieldsets = (
        ('업로드 제한 설정', {
            'fields': ('daily_upload_limit', 'ranker_limit_exempt_rank'),
            'description': '랭커 제한 해제 순위를 0으로 설정하면 비활성화됩니다.'
        }),
    )
    
    def has_add_permission(self, request):
        # 싱글톤: 하나만 존재
        return not SiteSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False
