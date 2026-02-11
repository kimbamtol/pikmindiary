from django.contrib import admin
from .models import Like, Bookmark, Notification


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'coordinate', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__nickname', 'coordinate__title']


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ['user', 'coordinate', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__nickname', 'coordinate__title']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'notification_type', 'message', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    list_editable = ['is_read']
    search_fields = ['recipient__nickname', 'message']
    raw_id_fields = ['recipient', 'actor', 'coordinate']
