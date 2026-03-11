from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='anton_index'),
    path('my-models/', views.my_models, name='my_models'),
]
