from django.urls import path
from . import views

app_name = 'farming'

urlpatterns = [
    # 메인 페이지
    path('', views.farming_home, name='home'),
    
    # 농사 일지
    path('journals/', views.journal_list, name='journal_list'),
    path('journals/new/', views.journal_create, name='journal_create'),
    path('journals/<int:pk>/', views.journal_detail, name='journal_detail'),
    path('journals/<int:pk>/edit/', views.journal_edit, name='journal_edit'),
    path('journals/<int:pk>/delete/', views.journal_delete, name='journal_delete'),
    path('journals/<int:pk>/like/', views.toggle_journal_like, name='toggle_journal_like'),
    
    # 농사 요청
    path('requests/', views.request_list, name='request_list'),
    path('requests/new/', views.request_create, name='request_create'),
    path('requests/<int:pk>/', views.request_detail, name='request_detail'),
    path('requests/<int:pk>/participate/', views.participate, name='participate'),
    path('requests/<int:pk>/complete/', views.complete_request, name='complete_request'),
    
    # 내 활동
    path('my/', views.my_farming, name='my_farming'),
]
