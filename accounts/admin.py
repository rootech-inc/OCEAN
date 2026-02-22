from django.contrib import admin
from .models import Ledger, PaymentVoucher, VoucherTransaction

admin.site.register(Ledger)
admin.site.register(PaymentVoucher)
admin.site.register(VoucherTransaction)
