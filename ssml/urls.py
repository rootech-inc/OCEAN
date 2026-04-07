"""ocean URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from . import views
from . import ssml_api  
from .api import contractor_api
from . import location_import_api

urlpatterns = [
    path('', views.index, name='ssml'),
    path('inventory/materials/', views.materials, name='materials'),
    # path('ssml/',include('ssml.urls')),
   
    path('master/retired_meters/',views.retired_meters,name='retired_meters'),
    path('accounts/finlog/',views.accounts,name='accounts'),
    path('accounts/ledger/',views.ledger,name='ssml_ledger'),
    path('accounts/jv/',views.journal_voucher,name='ssml_journal_voucher'),
    path('accounts/jv/new/',views.journal_voucher_add,name='ssml_journal_voucher_add'),
    path('accounts/invoice/',views.invoice,name='cont-invoice'),
    path('account/new-cont-inv/',views.invoice_new,name='new-cont-inv'),
    path('accounts/invoice/edit/<int:pk>/', views.invoice_edit, name='edit-cont-inv'),
    path('accounts/ecg-invoice/', views.ecg_invoice, name='ecg-invoice'),
    path('accounts/ecg-invoice/new/', views.ecg_invoice_new, name='new-ecg-inv'),
    path('accounts/ecg-invoice/edit/<int:pk>/', views.ecg_invoice_edit, name='edit-ecg-inv'),
    path('accounts/ecg-invoice/view/<int:pk>/', views.ecg_invoice_view, name='view-ecg-inv'),
    path('accounts/ecg-invoice/rates/', views.ecg_rates, name='ecg-rates'),
    path('accounts/petty-cash/',views.petty_cash,name='ssml-petty-cash'),
    path('accounts/upload-evidence/',views.financial_evidence,name='financial_evidence'),
    path('accounts/request/',views.request_expense,name='request_expense'),
   
    path('accounts/request/save/', views.save_expense_request, name='save_expense_request'),


    path('inventory/grn/', views.grn, name='grn'),
    path('inventory/grn/add/', views.grn_add, name='grn_add'),
    path('inventory/grn/edit/<int:id>/', views.grn_edit, name='grn_edit'),
    path('inventory/issue/', views.issue, name='issue'),
    path('inventory/issue/add/', views.issue_add, name='issue_add'),
    path('inventory/issue/edit/<int:id>/', views.issue_edit, name='issue_edit'),
    path('inventory/redeem/',views.redeem,name='redeem'),
    path('inventory/redeem/new/',views.new_redemption,name='new_redemption'),
    path('inventory/linked-models/',views.linked_models,name='linked_models'),
    path('inventory/material-request/',views.material_request,name='ssml_material_request'),
    path('inventory/material-request/new/',views.new_material_request_screen,name='ssml_new_material_request'),
    path('api/', ssml_api.interface, name='api'),
    path('upload_image/', views.upload_image, name='upload_image'),
    path('work-order/plots/', views.plots, name='plots'),
    path('work-order/services/', views.services, name='services'),
    path('work-order/service-orders/', views.service_orders, name='service_orders'),
    path('master/contractors/', views.contractors, name='contractors'),
    path('master/contractors/list/',views.contractor_list,name='contractor_list'),
    path('api/contractor/', contractor_api.contractor_api, name='contractors_api'),
    path('service-order/new/', views.service_order_new, name='service_order_new'),
    path('contractor-errors/', views.contractor_errors, name='contractor_errors'),
    path('contractor-errors/add/', views.save_contractor_error, name='save_contractor_error'),
    path('service-order/upload/',views.upload_service_order,name='upload_service_order'),
    path('service-type/view/<id>/',views.servive_type,name='service_type'),
    path('service-type/add-rate-to-type/',views.add_service_to_type,name='add_service_to_type'),
    path('material/add-rate/',views.add_material_rate,name='add_material_rate'),
    path('delete-service-rate/<id>/',views.delete_service_rate,name='delete-service-rate'),
    path('delete-service-type-rate/<id>/',views.delete_type_service_rate,name='delete_type_service_rate'),
    path('master/location_master/',views.location_master,name='ssml_location_master'),
    path('inventory/trenasfer/',views.transfer,name='ssml_transfer'),
    path('inventory/transfer/add/',views.add_transfer,name='ssml_add_transfer'),
    path('inventory/transfer/post/<entry_no>/',views.post_transfer,name='ssml_post_transfer'),
    path('sync_retired_meter/',views.sync_retired_meter,name='sync_retired_meter'),
    path('approve_document/',views.approve_document, name='ssml_approve_document'),
    path('foc-portal/',views.foc_portal,name='ssml_foc_portal'),
    path('foc-portal/my-company/',views.my_company,name='ssml_foc_compnay'),
    path('upload_contractor_docs/',views.upload_contractor_docs,name='ssml_upload_contractor_docs'),
    path('service/tools/', views.service_tools, name='ssml_service_tools'),
    path('forms/ulbm/',views.ulbm,name='ssml_form_ulbm'),# update boxing meta data
    path('inventory/cardex/<barcode>/',views.cardex, name='ssml_cardex'),
    path('import-expensis/',views.import_expensis,name='import-expensis'),
    ## meter master
     path('meters/',views.meters,name='meters'),
    path('meters/phase-master/',views.phase_master,name='phase-master'),
    path('meters/import-shipment-file/',views.import_shipment_file,name='import_shipment_file'),
    path('master/import-locations/', location_import_api.import_locations, name='import_locations'),
    path('ecg/reports/',views.ecg_reports,name='ecg_reports'),

]
