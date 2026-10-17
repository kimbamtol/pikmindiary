from django.contrib import admin
from django.utils.html import format_html

from .models import BragLike, BragPost


@admin.register(BragPost)
class BragPostAdmin(admin.ModelAdmin):
    list_display = ['thumb', 'display_name', 'caption', 'like_count', 'comment_count', 'is_hidden', 'created_at']
    list_filter = ['is_hidden', 'created_at']
    list_editable = ['is_hidden']
    search_fields = ['caption', 'guest_nickname', 'author__nickname']
    readonly_fields = ['like_count', 'comment_count', 'view_count', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:48px;border-radius:4px">', obj.image.url)
        return '-'
    thumb.short_description = '사진'


@admin.register(BragLike)
class BragLikeAdmin(admin.ModelAdmin):
    list_display = ['post', 'user', 'session_key', 'created_at']
    list_filter = ['created_at']
    readonly_fields = ['post', 'user', 'session_key', 'created_at']
