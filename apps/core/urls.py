"""Core app URLs - 랜딩 페이지 및 안내 페이지"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('guide/', views.guide_page, name='guide'),
    path('guide/mypage/', views.mypage_guide, name='mypage_guide'),
    path('api/default-location/', views.default_location, name='default_location'),
    path('suggestion/', views.suggestion_form, name='suggestion'),
    path('suggestion/done/', views.suggestion_done, name='suggestion_done'),
]
