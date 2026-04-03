"""Admin Panel app URLs - 관리자 대시보드"""
from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('pending/', views.pending_list, name='pending_list'),
    path('approve/<int:pk>/', views.approve_coordinate, name='approve'),
    path('reject/<int:pk>/', views.reject_coordinate, name='reject'),
    path('reports/', views.report_list, name='report_list'),
    path('reports/<int:pk>/resolve/', views.resolve_report, name='resolve_report'),
    
    # 관리자 관리 (슈퍼유저만)
    path('users/', views.user_list, name='user_list'),
    path('users/<int:pk>/toggle-staff/', views.toggle_staff, name='toggle_staff'),
    
    # 게시글 일괄 관리 & 정지 관리 (슈퍼유저만)
    path('batch/', views.batch_post_management, name='batch_post_management'),
    path('batch/delete/', views.batch_delete_posts, name='batch_delete_posts'),
    path('batch/ban/', views.ban_user, name='ban_user'),
    path('bans/', views.ban_list, name='ban_list'),
    path('bans/<int:pk>/unban/', views.unban_user, name='unban_user'),
]
