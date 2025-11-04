from django.urls import path 
from .views import * 

urlpatterns = [
    path('', GetDashboardData.as_view(), name='dashboard_report'),
    path('test', GetDashboardReport.as_view(), name='dashboard_report_test'),
    path('4p', GetFourPData.as_view(), name='4p_report'),
    path('v2', GetDashboardReport2.as_view(), name='dashboard_report_v2'),
]