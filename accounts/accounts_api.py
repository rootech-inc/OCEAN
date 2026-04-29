import json
import sys
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Model
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from accounts.models import Ledger, PaymentVoucher, VoucherTransaction, AccountType


def _gen_voucher_no():
    count = PaymentVoucher.objects.all().count() + 1
    return f"PV{str(count).zfill(7)}"


@csrf_exempt
def interface(request):
    response = {
        'status_code': 200,
        'message': 'OK'
    }
    success_response = {'status_code': 200, 'message': 'OK'}

    try:
        body = json.loads(request.body)
        module = body.get('module')
        data = body.get('data', {})
        method = request.method

        # ─── CREATE / UPDATE ───────────────────────────────────────────
        if method == 'PUT':

            if module == 'account_type':

                name = data.get('name')
                description  = data.get('description')
                normal_balance = data.get('normal_balance',"DR")
                created_by = User.objects.get(pk=data.get('mypk'))
                code = "AT1" if AccountType.objects.all().count() == 0 else f"AT{AccountType.objects.all().last().pk + 1}"


                AccountType.objects.create(
                    code=code,
                    name=name,
                    description=description,
                    normal_balance=normal_balance,
                    created_by=created_by
                )

                success_response['message'] = "Account Type created"
                response = success_response

            elif module == 'ledger':

                name = data.get('name')
                description = data.get('description', '')
                owner = User.objects.get(pk=data.get('mypk'))
                account_type = AccountType.objects.get(code=data.get('account_type'))
                code = "LE1" if Ledger.objects.all().count() == 0 else f"LE{Ledger.objects.all().last().pk + 1}"
                sledge = data.get('sledge',name.replace(' ','')).lower()

                ledger = Ledger(
                    code=code,
                    name=name,
                    description=description,
                    owner=owner,
                    account_type=account_type,
                    sledge=sledge
                )
                ledger.save()
                success_response['message'] = f"Ledger '{name}' created successfully"
                response = success_response

            elif module == 'create_voucher':
                recipient = data.get('recipient')
                phone = data.get('phone', '')
                email = data.get('email', '')
                remarks = data.get('remarks', '')
                ledger_pk = data.get('ledger_pk')
                items = data.get('items', [])

                ledger = Ledger.objects.get(pk=ledger_pk)

                # Calculate total
                total = sum(Decimal(str(i.get('amount', 0))) for i in items)

                # Validate against available ledger balance
                available = ledger.available_balance()
                if total > available:
                    response['status_code'] = 400
                    response['message'] = (
                        f"Insufficient ledger balance. "
                        f"Requested: {total:.2f}, Available: {available:.2f}"
                    )
                    return JsonResponse(response)

                voucher = PaymentVoucher(
                    voucher_no=_gen_voucher_no(),
                    recipient=recipient,
                    phone=phone,
                    email=email,
                    remarks=remarks,
                    ledger=ledger,
                    total_amount=total,
                    owner=request.user
                )
                voucher.save()

                for item in items:
                    VoucherTransaction(
                        voucher=voucher,
                        title=item.get('title', ''),
                        description=item.get('description', ''),
                        amount=Decimal(str(item.get('amount', 0)))
                    ).save()

                success_response['message'] = {
                    'voucher_no': voucher.voucher_no,
                    'pk': voucher.pk
                }

        # ─── PATCH ────────────────────────────────────────────────────
        elif method == 'PATCH':
            if module == 'approve_voucher':
                pk = data.get('pk')
                voucher = PaymentVoucher.objects.get(pk=pk)
                if voucher.is_approved:
                    response['status_code'] = 400
                    response['message'] = "Voucher already approved"
                    return JsonResponse(response)
                voucher.is_approved = True
                voucher.approved_by = request.user
                voucher.approved_date = timezone.now().date()
                voucher.save()
                success_response['message'] = "Voucher approved successfully"

            elif module == 'confirm_voucher':
                pk = data.get('pk')
                voucher = PaymentVoucher.objects.get(pk=pk)

                if not voucher.is_approved:
                    response['status_code'] = 400
                    response['message'] = "Voucher must be approved before confirmation"
                    return JsonResponse(response)

                if voucher.is_confirmed:
                    response['status_code'] = 400
                    response['message'] = "Voucher already confirmed"
                    return JsonResponse(response)

                # Re-validate balance at confirmation time
                ledger = voucher.ledger
                available = ledger.available_balance()
                if voucher.total_amount > available:
                    response['status_code'] = 400
                    response['message'] = (
                        f"Insufficient ledger balance at confirmation. "
                        f"Required: {voucher.total_amount:.2f}, Available: {available:.2f}"
                    )
                    return JsonResponse(response)

                voucher.is_confirmed = True
                voucher.confirmed_by = request.user
                voucher.confirmed_date = timezone.now().date()
                voucher.save()
                success_response['message'] = "Voucher confirmed. Ledger balance updated."

            elif module == 'update_ledger_balance':
                pk = data.get('pk')
                amount = Decimal(str(data.get('amount', 0)))
                action = data.get('action', 'add')  # 'add' or 'subtract'
                ledger = Ledger.objects.get(pk=pk)
                if action == 'add':
                    ledger.balance += amount
                else:
                    ledger.balance -= amount
                ledger.save()
                success_response['message'] = f"Ledger balance updated. New balance: {ledger.balance:.2f}"

        # ─── VIEW ─────────────────────────────────────────────────────
        elif method == 'VIEW':

            if module == 'account_type':
                code = data.get('code','*')

                success_response['message'] = [
                    act.obj() for act in (
                        AccountType.objects.all().order_by('name') if code == '*'
                        else AccountType.objects.filter(code=code)
                    )
                ]

            elif module == 'ledger':

                code = data.get('code', '*')

                success_response['message'] = [
                    act.obj() for act in (
                        Ledger.objects.all().order_by('name') if code == '*'
                        else Ledger.objects.filter(code=code)
                    )
                ]

            elif module == 'get_vouchers':
                vouchers = PaymentVoucher.objects.all().order_by('-pk')
                ledger_pk = data.get('ledger_pk')
                if ledger_pk:
                    vouchers = vouchers.filter(ledger_id=ledger_pk)

                arr = []
                for v in vouchers:
                    arr.append({
                        'pk': v.pk,
                        'voucher_no': v.voucher_no,
                        'recipient': v.recipient,
                        'phone': v.phone,
                        'email': v.email,
                        'ledger': v.ledger.name,
                        'ledger_pk': v.ledger.pk,
                        'total_amount': float(v.total_amount),
                        'is_approved': v.is_approved,
                        'approved_by': v.approved_by.get_full_name() if v.approved_by else '',
                        'is_confirmed': v.is_confirmed,
                        'confirmed_by': v.confirmed_by.get_full_name() if v.confirmed_by else '',
                        'status': v.status_label(),
                        'created_date': str(v.created_date),
                        'receipt': v.receipt.url if v.receipt else None,
                    })
                success_response['message'] = arr

            elif module == 'get_voucher_details':
                pk = data.get('pk')
                v = PaymentVoucher.objects.get(pk=pk)
                items = [
                    {
                        'pk': t.pk,
                        'title': t.title,
                        'description': t.description,
                        'amount': float(t.amount)
                    }
                    for t in v.items.all()
                ]
                success_response['message'] = {
                    'pk': v.pk,
                    'voucher_no': v.voucher_no,
                    'recipient': v.recipient,
                    'phone': v.phone,
                    'email': v.email,
                    'remarks': v.remarks,
                    'ledger': {'pk': v.ledger.pk, 'name': v.ledger.name},
                    'total_amount': float(v.total_amount),
                    'is_approved': v.is_approved,
                    'approved_by': v.approved_by.get_full_name() if v.approved_by else '',
                    'approved_date': str(v.approved_date) if v.approved_date else '',
                    'is_confirmed': v.is_confirmed,
                    'confirmed_by': v.confirmed_by.get_full_name() if v.confirmed_by else '',
                    'confirmed_date': str(v.confirmed_date) if v.confirmed_date else '',
                    'status': v.status_label(),
                    'created_date': str(v.created_date),
                    'created_time': str(v.created_time),
                    'owner': v.owner.get_full_name() or v.owner.username,
                    'receipt': v.receipt.url if v.receipt else None,
                    'items': items,
                }

        else:
            success_response['status_code'] = 505
            success_response['message'] = f"Unknown method: {method}"

        response = success_response

    except Exception as e:
        error_type, error_instance, traceback = sys.exc_info()
        tb_path = traceback.tb_frame.f_code.co_filename
        line_number = traceback.tb_lineno
        success_response['status_code'] = 500
        success_response['message'] = (
            f"Error [{error_type.__name__}] on line {line_number} in {tb_path}: {e}"
        )

    return JsonResponse(success_response)
