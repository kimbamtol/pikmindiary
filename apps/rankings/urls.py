"""Rankings app URLs - 랭킹"""
from django.urls import path
from . import views

app_name = 'rankings'

urlpatterns = [
    path('', views.ranking_list, name='list'),
    path('weekly/', views.weekly_ranking, name='weekly'),
    path('monthly/', views.monthly_ranking, name='monthly'),
]
