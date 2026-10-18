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

    # 새 디자인(수첩) 체험
    path('design/beta/on/', views.design_beta_on, name='design_beta_on'),
    path('design/beta/off/', views.design_beta_off, name='design_beta_off'),
    path('design/popup/dismiss/', views.design_popup_dismiss, name='design_popup_dismiss'),
    path('design/vote/', views.design_vote, name='design_vote'),

    # 목록 보기 방식
    path('display/density/', views.set_list_density, name='set_list_density'),
]
