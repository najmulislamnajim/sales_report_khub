from django.urls import path 
from .views import * 

urlpatterns = [
    path('dashboard', GetDashboardData.as_view(), name='dashboard_report'),
]