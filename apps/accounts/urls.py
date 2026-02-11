"""Accounts app URLs - 마이페이지"""
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('my/', views.my_page, name='my_page'),
    path('my/posts/', views.my_posts, name='my_posts'),
    path('my/bookmarks/', views.my_bookmarks, name='my_bookmarks'),
    path('my/settings/', views.my_settings, name='my_settings'),
    path('my/suggestions/', views.my_suggestions, name='my_suggestions'),
    path('my/comments/', views.my_comments, name='my_comments'),
    path('profile/<int:user_id>/', views.user_profile, name='user_profile'),
]
