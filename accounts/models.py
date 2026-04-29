from attr.validators import max_len
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from django.utils import timezone

class AccountType(models.Model):
    code = models.CharField(max_length=10, unique=True, null=False, blank=False)
    name = models.CharField(max_length=255, unique=True, null=False, blank=False)
    description = models.TextField(blank=True, null=True)
    NORMAL_BALANCE_CHOICES = [
        ('DR', 'Debit'),
        ('CR', 'Credit'),
    ]
    normal_balance = models.CharField(max_length=2, choices=NORMAL_BALANCE_CHOICES, default='DR')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.code} - {self.name}"

    def balance(self):
        return 0

    def obj(self):
        return {
            'code':self.code,
            'name':self.name,
            'description':self.description,
            'normal_balance':self.normal_balance,
            'created_by':self.created_by.get_full_name() if self.created_by else '',
            'balance':self.balance()
        }




class Ledger(models.Model):
    account_type = models.ForeignKey(AccountType, on_delete=models.PROTECT, related_name='ledgers')
    code = models.CharField(max_length=10, unique=True, null=False, blank=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts_ledgers_top')
    created_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    sledge = models.CharField(max_length=255,null=False,unique=True,blank=False)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = (('account_type','name'))

    def obj(self):
        return {
            'code':self.code,
            'account_type':self.account_type.obj(),
            'name':self.name,
            'description':self.description,
            'owner': self.owner.get_full_name() if self.owner else '',
            'balance':self.balance,
            'pk':self.pk
        }



class SubLedger(models.Model):
    ledger = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name='subledgers')
    code = models.CharField(max_length=10, unique=True, null=False, blank=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts_ledgers')


class JVHeader(models.Model):
    voucher_no = models.CharField(max_length=50, unique=True) # e.g., JV-2026-0001
    date = models.DateField()
    narration = models.TextField() # General description of the whole event
    # total_amount = models.DecimalField(max_digits=20, decimal_places=2)
    prepared_by = models.ForeignKey(User, on_delete=models.PROTECT)
    is_posted = models.BooleanField(default=False) # Draft vs. Finalized
    created_at = models.DateTimeField(auto_now_add=True)
    ref = models.CharField(max_length=255,null=False,blank=False)

    def __str__(self):
        return f"{self.voucher_no} - {self.date}"


class JVTransaction(models.Model):
    header = models.ForeignKey(JVHeader, related_name='items', on_delete=models.CASCADE)

    # Links to Ledger via 'code' as you requested
    ledger = models.ForeignKey(
        'Ledger',
        to_field='code',
        on_delete=models.PROTECT
    )
    sub_ledger = models.ForeignKey(
        'SubLedger',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    # Use two fields instead of a type choice
    debit = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)

    line_description = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(User,models.PROTECT, related_name='transactions_by',null=True)

    def __str__(self):
        return f"{self.header.voucher_no} | {self.type} | {self.amount}"

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

