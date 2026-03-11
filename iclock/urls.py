
from . import views, iclock_api
from django.urls import path
urlpatterns = [
    path('cdata', views.handle_cdata),
    path('getrequest', views.handle_heartbeat),
    path('devicecmd', views.handle_device_command),
    path('ping', views.handle_ping),
    path('api/', iclock_api.api_interface, name='iclock_api'),
]