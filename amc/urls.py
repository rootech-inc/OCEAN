
from . import views
from . import api
from django.urls import path
urlpatterns = [
    
    path('',views.amc,name='asset_management_center'),
    path('groups/',views.groups,name='amc_groups'),
    path('api/',api.amc_interface,name='amc_api'),
    path('upload_image/',views.upload_asset_image,name='upload_asset_image'),
    path('sign-recieved/',views.sign_reciept,name='amc_signed_reciept'),
    path('group/<name>/',views.asset_group,name='amc_asset_group'),
    path('compliance/',views.compliance,name='amc_compliance'),
    path('compliance/authorities/',views.compliance_authorities,name='amc_compliance_authorities'),
    path('authority/upload-logo/',views.upload_auth_logo,name='amc_upload_auth_logo'),

    path('compliance/type/',views.compliance_type,name='amc_compliance_type'),
    path('upload/asset_compliance_document/',views.upload_asset_compliance_document,name='upload_asset_compliance_document'),
]