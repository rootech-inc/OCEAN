from django.urls import path
from . import views, accounts_api

urlpatterns = [
    path('', views.index, name='accounts_index'),
    path('vouchers/', views.vouchers, name='accounts_vouchers'),
    path('account-types/', views.account_types, name='accounts_account_types'),
    path('ledgers/', views.ledgers, name='accounts_ledgers'),
    path('journal-voucher/', views.journal_voucher, name='accounts_journal_voucher'),
    path('journal-voucher/create/', views.journal_voucher_create, name='accounts_journal_voucher_create'),
    path('api/', accounts_api.interface, name='accounts_api'),
    path('voucher/print/<int:pk>/', views.print_voucher, name='accounts_print_voucher'),
]
