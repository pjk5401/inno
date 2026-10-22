from django.conf import settings
from django.urls import include, path

urlpatterns = [path('test/' if settings.SANDBOX else '', include('attendance.urls'))]
