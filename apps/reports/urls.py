"""Reports app URLs - 신고"""
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('coordinate/<int:coordinate_id>/', views.report_coordinate, name='report_coordinate'),
    path('comment/<int:comment_id>/', views.report_comment, name='report_comment'),
]
