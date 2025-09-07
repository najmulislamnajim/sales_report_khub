from django.urls import path 
from .views import * 

urlpatterns = [
    path('', GetDashboardData.as_view(), name='dashboard_report'),
    path('test', GetDashboardReport.as_view(), name='dashboard_report_test'),
]