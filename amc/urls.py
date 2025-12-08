
from . import views
from . import api
from django.urls import path
urlpatterns = [
    
    path('',views.amc,name='asset_management_center'),
    path('groups/',views.groups,name='amc_groups'),
    path('api/',api.amc_interface,name='amc_api')
]