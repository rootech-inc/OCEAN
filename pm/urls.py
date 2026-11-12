from django.urls import path

from pm import views, pm_api

urlpatterns = [
    path('', views.index, name='pm_index'),
    path('clients/', views.clients, name='pm_clients'),
    path('projects/<str:url>/', views.project_detail, name='pm_project_detail'),
    path('upload-client-logo/', views.upload_client_logo, name='pm_upload_client_logo'),
    path('upload-project-cover/', views.upload_project_cover, name='pm_upload_project_cover'),
    path('api/', pm_api.index, name='pm_api'),
]
