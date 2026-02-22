from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class Ledger(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts_ledgers')
    created_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def spent(self):
        """Total confirmed amount drawn from this ledger."""
        return PaymentVoucher.objects.filter(
            ledger=self, is_confirmed=True
        ).aggregate(total=Sum('total_amount'))['total'] or 0.00

    def available_balance(self):
        return self.balance - self.spent()


class PaymentVoucher(models.Model):
    voucher_no = models.CharField(max_length=20, unique=True)
    recipient = models.CharField(max_length=255)
    phone = models.CharField(max_length=30, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    ledger = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name='vouchers')
    total_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)

    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_vouchers'
    )
    approved_date = models.DateField(null=True, blank=True)

    is_confirmed = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_vouchers'
    )
    confirmed_date = models.DateField(null=True, blank=True)

    receipt = models.ImageField(upload_to='accounts/receipts/', null=True, blank=True)

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_vouchers')
    created_date = models.DateField(auto_now_add=True)
    created_time = models.TimeField(auto_now_add=True)

    def __str__(self):
        return self.voucher_no

    def transactions(self):
        return VoucherTransaction.objects.filter(voucher=self)

    def computed_total(self):
        return self.transactions().aggregate(total=Sum('amount'))['total'] or 0.00

    def status_label(self):
        if self.is_confirmed:
            return 'Confirmed'
        if self.is_approved:
            return 'Approved'
        return 'Pending'


class VoucherTransaction(models.Model):
    voucher = models.ForeignKey(PaymentVoucher, on_delete=models.CASCADE, related_name='items')
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.voucher.voucher_no} — {self.title}"
