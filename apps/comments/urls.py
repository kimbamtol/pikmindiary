"""Comments app URLs - 댓글"""
from django.urls import path
from . import views

app_name = 'comments'

urlpatterns = [
    # 좌표 댓글
    path('create/<int:coordinate_id>/', views.comment_create, name='create'),
    path('<int:pk>/edit/', views.comment_edit, name='edit'),
    path('<int:pk>/delete/', views.comment_delete, name='delete'),
    path('<int:pk>/reply/', views.comment_reply, name='reply'),
    
    # 농사 일지 댓글
    path('journal/<int:journal_id>/create/', views.journal_comment_create, name='journal_create'),
    path('journal/<int:pk>/reply/', views.journal_comment_reply, name='journal_reply'),
]
