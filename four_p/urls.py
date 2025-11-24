from django.urls import path
from .views import GetFourPDetails

urlpatterns = [
    path("details", GetFourPDetails.as_view(), name="get_4p_details"),
]
