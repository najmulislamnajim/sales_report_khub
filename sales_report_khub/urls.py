from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/user/',include('myuser.urls')),
    path('api/v1/reports/',include('reports_app.urls')),
]
