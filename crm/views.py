from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from admin_panel.anton import is_valid_phone_number, is_valid_email, fix_phone_number
from admin_panel.models import SmsApi, MailSenders
from crm.models import Logs, CrmUsers, FollowUp, LeadStreams, Contacts


# Create your views here.
@login_required()
def base(request):
    # if request.user.is_superuser:
    #     logs = Logs.objects.filter(created_date=timezone.now().date()).order_by('-pk')
    # else:
    #     logs = Logs.objects.filter(owner=request.user, created_date=timezone.now().date()).order_by('-pk')
    logs = Logs.objects.filter(owner=request.user, created_date=timezone.now().date()).order_by('-pk')
    context = {
        'nav': True,
        'page': {
            'title': "CRM",
        },
        'logs': logs,
        'followup':FollowUp.objects.filter(owner=request.user, is_open=True,follow_date__lt=timezone.now().date()).count(),
    }

    return render(request, 'crm/index.html', context=context)

@login_required()
def crm_logs(request):
    pend_val = Logs.objects.filter(created_date=timezone.now().date(), validity=99)
    val_val = Logs.objects.filter(created_date=timezone.now().date(), validity=1)
    not_val = Logs.objects.filter(created_date=timezone.now().date(), validity=0)

    if request.user.is_superuser:
        logs = Logs.objects.filter(created_date=timezone.now().date()).order_by('-pk')
    else:
        logs = Logs.objects.filter(owner=request.user, created_date=timezone.now().date()).order_by('-pk')
        pend_val.filter(owner=request.user)
        val_val.filter(owner=request.user)
        not_val.filter(owner=request.user)



    context = {
        'nav': True,
        'page': {
            'title': "CRM",
        },
        'logs': logs,
        'followup': FollowUp.objects.filter(owner=request.user, is_open=True,
                                            follow_date__lt=timezone.now().date()).count(),
        'val':{
            'pend':pend_val.count(),
            'val':val_val.count(),
            'nott':not_val.count(),
        }

    }

    return render(request, 'crm/logs.html', context=context)

@login_required()
def follows(request):
    if request.user.is_superuser:
        logs = FollowUp.objects.filter(is_open=True).order_by('-pk')
    else:
        logs = FollowUp.objects.filter(owner=request.user, is_open=True).order_by('-pk')
    context = {
        'nav': True,
        'page': {
            'title': "CRM Follow Up",
        },
        'logs': logs
    }

    return render(request, 'crm/follow.html', context=context)

@login_required()
def crm_users(request):
    context = {
        'nav': True,
        'page': {
            'title': "CRM USERS",
        },
        'users': CrmUsers.objects.all().order_by('-pk')
    }

    return render(request, 'crm/crm-users.html', context=context)

@login_required()
def crm_tools(request):
    context = {
        'nav': True,
        'page': {
            'title': "CRM TOOLS",
        },
        'users': CrmUsers.objects.all().order_by('-pk')
    }

    return render(request, 'crm/crm-tools.html', context=context)

@login_required()
def contacts(request):
    return render(request, 'crm/contacts.html', context={
        'nav': True,
        'page': {'title': "CRM Contacts"}
    })

@login_required()
def campaigns(request):
    return render(request, 'crm/campaigns.html', context={
        'nav': True,
        'page': {'title': "Campaigns"}
    })

@login_required()
def new_campaign(request):
    return render(request, 'crm/campaigns-new.html', context={
        'nav': True,
        'page': {'title': "New Campaigns"},
        'smsapis': SmsApi.objects.all(),
        'mss':MailSenders.objects.all()
    })

@login_required()
def crm_lead_stream(request):

    return render(
        request,
        'crm/lead_stram.html',
        context={
            'nav': True,
            'page': {'title': "CRM Lead Stream"},
            'leads':LeadStreams.objects.all(),
        }
    )



@csrf_exempt  # Assuming AJAX or fetch, remove if not necessary
@login_required()
def upload_contacts(request):
    import pandas as pd
    if request.method == "POST":
        excel_file = request.FILES.get('excel_file')
        contact_type = request.POST.get('contact_type')
        not_done = []
        if not excel_file:
            not_done.append('excel_file')
        if not contact_type:
            not_done.append('contact_type')
        if not_done:
            return JsonResponse({'success': False, 'message': f"Required fields missing: {', '.join(not_done)}.", 'not_done': not_done})

        try:
            # Read the uploaded file into a dataframe
            df = pd.read_excel(excel_file)

            required_columns = ['name', 'contact']
            if not all(col in df.columns for col in required_columns):
                return JsonResponse({'success': False, 'message': "Excel missing required columns: name, contact, source"})

            count = 0
            for _, row in df.iterrows():
                name = row.get('name', '') or ''

                # Get the raw value
                raw_contact = row.get('contact', '')

                # Format: ensure it's an integer (to remove .0) then pad to 10 digits
                if pd.notnull(raw_contact) and raw_contact != '':
                    contact = f"{int(raw_contact):010d}"
                else:
                    contact = ''
                    
                source = 'upd'

                contact = fix_phone_number(contact) if contact == 'sms' else contact
                print(f"Contact: {contact}")

                if name and contact:
                    if contact_type == 'sms' and is_valid_phone_number(str(contact)):
                        Contacts.objects.create(
                            name=name,
                            contact=contact,
                            source=source,
                            type=contact_type
                        )

                        count += 1
                    elif contact_type == 'email' and is_valid_email(str(contact)):
                        Contacts.objects.create(
                            name=name,
                            contact=contact,
                            source=source,
                            type=contact_type
                        )
                        count += 1

            return JsonResponse({'success': True, 'message': f"{count} contacts uploaded."})

        except Exception as e:
            import sys
            tb = sys.exc_info()[2]
            line_no = tb.tb_lineno if tb else 'unknown'
            return JsonResponse({'success': False, 'message': f"Upload failed at line {line_no}: {str(e)}"}, status=400)
    else:
        return redirect('crm')
