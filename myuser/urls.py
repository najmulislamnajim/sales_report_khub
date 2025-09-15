from django.urls import path
from .views import *

urlpatterns = [
    path('login',LoginView.as_view(), name='login'),
    path('brands',GetBrands.as_view(), name='get_brands'),
    path('next-user-list',GetNextUserList.as_view(), name='get_next_user_list'),
    path('info/<str:work_area_t>',GetUserInfo.as_view(), name='get_user_info'),
]
