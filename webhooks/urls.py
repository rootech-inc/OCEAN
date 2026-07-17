from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from ocean import settings
from webhooks import views

urlpatterns = [
    path('',views.index,name='webhooks'),
    path("whatsapp/", views.whatsapp_webhook, name="whatsapp_webhook"),

]