"""Coordinates app URLs - 좌표 게시글 CRUD"""
from django.urls import path
from . import views

app_name = 'coordinates'

urlpatterns = [
    path('', views.coordinate_list, name='list'),
    path('map/', views.map_view, name='map'),
    path('new/', views.coordinate_create, name='create'),
    path('<int:pk>/', views.coordinate_detail, name='detail'),
    path('<int:pk>/edit/', views.coordinate_edit, name='edit'),
    path('<int:pk>/delete/', views.coordinate_delete, name='delete'),
    path('<int:pk>/copy-coords/', views.copy_coords, name='copy_coords'),
]
