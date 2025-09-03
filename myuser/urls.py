from django.urls import path
from .views import *

urlpatterns = [
    path('login',LoginView.as_view(), name='login'),
    path('brands',GetBrands.as_view(), name='get_brands'),
]
