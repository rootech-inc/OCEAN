from django.urls import path
from . import views, accounts_api

urlpatterns = [
    path('', views.ledgers, name='accounts_ledgers'),
    path('vouchers/', views.vouchers, name='accounts_vouchers'),
    path('api/', accounts_api.interface, name='accounts_api'),
    path('voucher/print/<int:pk>/', views.print_voucher, name='accounts_print_voucher'),
]
