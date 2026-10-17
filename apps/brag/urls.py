"""Brag app URLs - 피크민 자랑"""
from django.urls import path

from . import views

app_name = 'brag'

urlpatterns = [
    path('', views.brag_list, name='list'),
    path('new/', views.brag_create, name='create'),
    path('<int:pk>/', views.brag_detail, name='detail'),
    path('<int:pk>/delete/', views.brag_delete, name='delete'),
    path('<int:pk>/like/', views.toggle_brag_like, name='like'),
    path('<int:pk>/comment/', views.brag_comment, name='comment'),
]
