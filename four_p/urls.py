from django.urls import path
from .views import GetFourPDetails, GetFourPData

urlpatterns = [
    path("details", GetFourPDetails.as_view(), name="get_4p_details"),
    path("details/v2", GetFourPData.as_view(), name="get_4p_details_v2"),
]
