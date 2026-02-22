from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.models import Ledger, PaymentVoucher

context = {
    'nav': True,
    'page': {'title': 'Accounts'}
}


@login_required()
def ledgers(request):
    context['page']['title'] = 'Ledgers'
    return render(request, 'accounts/ledgers.html', context)


@login_required()
def vouchers(request):
    context['ledgers'] = Ledger.objects.filter(is_active=True).order_by('name')
    context['page']['title'] = 'Payment Vouchers'
    return render(request, 'accounts/vouchers.html', context)


def print_voucher(request, pk):
    """Print / PDF-ready view — no login guard so it can be opened in new tab."""
    from django.conf import settings as django_settings
    voucher = PaymentVoucher.objects.get(pk=pk)
    context = {
        'voucher': voucher,
        'items': voucher.items.all(),
        'company': getattr(django_settings, 'COMPANY_DETAILS', {}),
    }
    return render(request, 'accounts/print_voucher.html', context)
