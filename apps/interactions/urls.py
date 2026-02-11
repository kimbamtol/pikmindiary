"""Interactions app URLs - 좋아요, 북마크, 알림"""
from django.urls import path
from . import views

app_name = 'interactions'

urlpatterns = [
    path('like/<int:coordinate_id>/', views.toggle_like, name='toggle_like'),
    path('comment-like/<int:comment_id>/', views.toggle_comment_like, name='toggle_comment_like'),
    path('bookmark/<int:coordinate_id>/', views.toggle_bookmark, name='toggle_bookmark'),
    # 알림 API
    path('notifications/', views.get_notifications, name='get_notifications'),
    path('notifications/unread-count/', views.get_unread_count, name='get_unread_count'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/delete-all/', views.delete_all_notifications, name='delete_all_notifications'),
]
