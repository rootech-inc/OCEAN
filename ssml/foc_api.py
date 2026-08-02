import json
import sys

from django.db.models import Model
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from admin_panel.anton import make_md5_hash
from admin_panel.models import MailQueues, MailSenders, Sms, SmsApi
from ssml.models import Contractor, Issue, FocInvoiceHd, FocInvoiceTransactions, FocInvoiceAssets, Agents, Retiring


@csrf_exempt
def interface(request):
    success_response = {
        'status_code': 200,
        'message': "Procedure Completed Successfully"
    }

    # get method
    method = request.method

    try:
        body = json.loads(request.body)
        module = body.get('module')
        data = body.get('data')

        if method == 'PUT':
            if module == 'validate_invoice':
                foc_code = data.get('foc_code')
                invoice_no = data.get('entry_no')

                foc = Contractor.objects.get(code=foc_code)

                invoice = FocInvoiceHd.objects.get(foc=foc,entry_no=invoice_no)

                # check if it is validate
                if not invoice.is_valid:
                    raise Exception(f"Invoice {invoice_no} is not validated")

                # check if it is accepted
                if invoice.is_accepted:
                    raise Exception(f"Invoice {invoice_no} accepted on {invoice.date_accepted}")

                accept_status = data.get('accept_status')
                accept = False
                ms = "Rejected"
                remarks = data.get('remark')
                is_valid = False

                if accept_status == 'YES':
                    accept = True
                    ms = "Accepted"
                    is_valid = True

                invoice.is_accepted = accept
                invoice.date_accepted = timezone.now().date()
                invoice.is_valid = is_valid
                invoice.accept_remark = remarks

                # make email
                for_management = f"Invoice {invoice_no} has been {ms} by FOC, with remarks f{remarks}"
                for_foc = f"You have {ms} invoice with remakes {remarks}"

                invoice.save()

                # Que Mail
                MailQueues.objects.create(
                    sender=MailSenders.objects.get(is_default=True),
                    recipient="accounts4@snedamotors.com",
                    cc='',
                    body=for_management,
                    mail_key=make_md5_hash(invoice.remarks),
                    subject=f"SNEDA - {invoice_no} - {ms}",
                )

                MailQueues.objects.create(
                    sender=MailSenders.objects.get(is_default=True),
                    recipient=foc.email,
                    cc='',
                    body=for_foc,
                    mail_key=make_md5_hash(f"{invoice.remarks}{for_foc}"),
                    subject=f"SNEDA - {invoice_no} - {ms}",
                )

                success_response['message'] = f"Invoice {ms}"

            elif module == 'agent':
                first_name = data.get('first_name')
                last_name = data.get('last_name')
                phone = data.get('phone')
                email = data.get('email')
                ghana_card = data.get('ghana_card')
                foc = data.get('foc_code')
                foc = Contractor.objects.get(code=foc)

                Agents.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    email=email,
                    foc=foc,
                    ghana_card=ghana_card
                )

                foc_sms = (f"Dear {first_name} {last_name}, your data has been submitted by {foc.company} to add as agent, review your information below\n"
                           f"Name: {first_name} {last_name}\nEmail:{email}\nGhana Card: {ghana_card}")
                Sms.objects.create(
                    api=SmsApi.objects.get(is_default=True),
                    to=phone,
                    message=foc_sms
                )

                success_response['message'] = "Agent Submitted"


            elif module == 'retirement':
                agent_code = data.get('agent_code')
                old_meter = data.get('old_meter')
                new_meter = data.get('new_meter')
                final_readings = data.get('final_readings')

                # todo:: validate meter belonging

                Retiring.objects.create(
                    agent=Agents.objects.get(code=agent_code),
                    old_meter = old_meter,
                    new_meter = new_meter,
                    final_reading=final_readings
                )

                success_response['message'] = "Process Completed"


            else:
                raise Exception("Invalid Something")



        elif method == 'VIEW':
            if module == 'dashboard':

                foc_code = data.get('foc_code')
                foc = Contractor.objects.get(code=foc_code)
                start_date = data.get('start_date','2000-01-01')
                end_date = data.get('end_date',timezone.now().date())
                success_response['message'] = foc.dashboard(start_date,end_date)

            elif module == 'list_way_bills':
                foc_code = data.get('foc_code')
                foc = Contractor.objects.get(code=foc_code)
                start_date = data.get('start_date', '2000-01-01')
                end_date = data.get('end_date', timezone.now().date())
                success_response['message'] = foc.waybill(start_date, end_date)

            elif module == 'get_waybill':
                foc_code = data.get('foc_code')
                foc = Contractor.objects.get(code=foc_code)
                issue_no = data.get('issue_no')

                issue = Issue.objects.get(issue_no=issue_no,contractor=foc)
                success_response['message'] = issue.obj()

            elif module == 'my_invoices':
                foc_code = data.get('foc_code')
                foc = Contractor.objects.get(code=foc_code)

                start_date = data.get('start_date', '2000-01-01')
                end_date = data.get('end_date', timezone.now().date())

                success_response['message'] = foc.invoices(start_date,end_date)

            elif module == 'invoice':
                foc_code = data.get('foc_code')
                foc = Contractor.objects.get(code=foc_code)

                entry_no = data.get('invoice')

                invoice = FocInvoiceHd.objects.get(entry_no=entry_no,foc=foc)
                success_response['message'] = {
                    'header':invoice.obj(),
                    'transactions':[tr.obj() for tr in FocInvoiceTransactions.objects.filter(invoice=invoice)],
                    'services':[srv.obj() for srv in FocInvoiceAssets.objects.filter(invoice=invoice)],
                }

            elif module == 'inventory':
                foc_code = data.get('foc_code')
                foc = Contractor.objects.get(code=foc_code)

                success_response['message'] = foc.inventory()

            elif module == 'my_compliance':
                foc_code = data.get('foc_code')
                foc = Contractor.objects.get(code=foc_code)
                success_response['message'] = foc.compliance()

            elif module == 'my_profile':
                success_response['message'] = Contractor.objects.get(code=data.get('foc_code')).minimal_obj()

            elif module == 'agent':
                foc = Contractor.objects.get(code=data.get('foc_code'))
                success_response['message'] = [ag.obj() for ag in Agents.objects.filter(foc=foc)]

            elif module == 'agent_otp':
                phone = data.get('phone')
                if Contractor.objects.filter(phone=phone).exists():
                    # generate opt
                    import random
                    otp = random.randint(101010, 999999)

                    contractor = Agents.objects.get(phone=phone)
                    if contractor.code is None:
                        raise Exception("Agent Not Approved")
                    contractor.otp = otp
                    ag_email = contractor.email
                    contractor.save()

                    # Send OTP via SMS
                    to = phone.replace('233', '0').replace('+233', '0')
                    messta = f"Your OTP code is: {otp}"
                    if len(to) == 10:
                        sms_message = messta
                        Sms(
                            api=SmsApi.objects.get(sender_id='SNEDA SML') if SmsApi.objects.filter(
                                sender_id='SNEDA SML').exists() else SmsApi.objects.get(is_default=True),
                            to=to,
                            message=sms_message
                        ).save()

                        MailQueues.objects.create(
                            sender=MailSenders.objects.get(is_default=True),
                            body=messta,
                            recipient=ag_email,
                            mail_key=make_md5_hash(f"{messta}{to}{ag_email}"),
                            subject="Sneda SML OTP Verification"
                        )

                    success_response['message'] = otp

            elif module == 'verify_agent_otp':
                    foc_verify_token = data.get('code')
                    print(data)
                    print(foc_verify_token)
                    if Agents.objects.filter(otp=foc_verify_token).exists():
                        contractor = Agents.objects.get(otp=foc_verify_token)
                        c_code = contractor.code
                        code = c_code
                        phone = contractor.phone
                        contractor.otp = None
                        contractor.save()
                        success_response['message'] = Agents.objects.get(phone=phone).obj()
                    else:
                        raise Exception("Invalid OTP")

            elif module == 'retirement':
                agent_code = data.get('agent_code')
                agent = Agents.objects.get(code=agent_code)
                success_response['message'] = agent.pending_retirement()

            else:
                raise Exception(f"Invalid Module {module}")

        elif method == 'PATCH':

            if module == 'account':
                foc_code = data.get('foc_code')
                foc = Contractor.objects.get(code=foc_code)
                foc.company = data.get('company')
                foc.owner = data.get('owner')

                foc.phone = data.get('phone')
                foc.email = data.get('email')
                foc.country = data.get('country')
                foc.city = data.get('city')
                foc.postal_code = data.get('postal_code')
                foc.gh_post_code = data.get('gh_post_code')

                foc.gh_card_no = data.get('gh_card_no')
                foc.link = data.get('link')
                foc.owner_phone = data.get('owner_phone')
                foc.owner_email = data.get('owner_email')
                foc.comp_reg_number = data.get('comp_reg_number')

                foc.business_type = data.get('business_type')
                foc.region = data.get('region')
                foc.business_address = data.get('business_address')
                foc.business_phone_number = data.get('business_phone_number')
                foc.business_email = data.get('business_email')

                foc.bank_name = data.get('bank_name')
                foc.bank_acct_number = data.get('bank_acct_number')
                foc.bank_branch = data.get('bank_branch')

                foc.save()

                success_response['message'] = "Your account has been updated successfully"

            else:
                raise Exception("Invalid Module")




        else:
            raise Exception("Invalid Mothod")





    except Exception as e:
        error_type, error_instance, traceback = sys.exc_info()
        tb_path = traceback.tb_frame.f_code.co_filename
        line_number = traceback.tb_lineno
        success_response["status_code"] = 500
        success_response[
            "message"] = f"An error occurred on line {line_number} in file {tb_path}. Details: {e}"

    return JsonResponse(success_response, safe=False)