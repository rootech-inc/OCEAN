
from django.db.models import Count, Sum, Model
from datetime import datetime, date
from decimal import Decimal
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from admin_panel.models import Emails, Locations, BusinessEntityTypes, MailSenders, MailQueues, MailAttachments, Sms, \
    SmsApi
from admin_panel.anton import make_md5_hash
from amc.models import ComplianceType
from crm.views import contacts

from ssml.form import ContractorErrorForm
from ssml.models import Contractor, ContractorError, Grn, GrnTransaction, InventoryMaterial, InvoiceHD, Issue, \
    IssueTransaction, Location, MaterialOrderItem, Meter, Plot, Reedem, RequiredReturn, Service, ServiceMaterialRates, \
    ServiceMaterials, ServiceOrder, \
    ServiceOrderItem, ServiceType, ServiceTypeServices, Supplier, TransferHd, Documents, ContractorDocuments, PettyCash, \
    RetiredMetersBox, InstallationType, Cardex, Phase, MaterialRequestHeader, \
    AccountLedger, RetiredMetersTransactions, FocInvoiceHd, JournalVoucherHd, \
    FocComplianceType, FocCompliance, Agents, Retiring
from dolphine.models import Documents


# Create your views here.
@login_required
def index(request):
    page = {
        'title': 'SSML',
        'page': 'ssml',
        'page_title': 'SSML',
        'page_description': 'SSML',
        'page_icon': 'bi bi-app',
        'page_url': 'ssml',
        'page_url_name': 'SSML',
        'nav':True
    }

    context = {
        'page': page
    }
    context['installations'] = ServiceType.objects.all()
    context['total_installs'] = ServiceOrder.objects.all().count()
    context['today_installs'] = ServiceOrder.objects.filter(service_date=datetime.now().date()).count()
    context['materials'] = InventoryMaterial.objects.all()
    context['locations'] = Location.objects.all().order_by('loc_name')
    
    # Calculate stock ready for re-order
    reorder_materials = []
    active_materials = InventoryMaterial.objects.filter(is_active=True, reorder_qty__gt=0)
    for mat in active_materials:
        current_stock = mat.stock()
        if current_stock <= mat.reorder_qty:
            reorder_materials.append({
                'material': mat,
                'stock': current_stock
            })
    context['reorder_materials'] = reorder_materials

    # Advanced Dashboard Metrics
    total_service_orders = ServiceOrder.objects.count()
    first_service_order = ServiceOrder.objects.order_by('service_date').first()
    
    avg_per_day = 0
    avg_per_month = 0
    
    if first_service_order and total_service_orders > 0:
        days_diff = (date.today() - first_service_order.service_date).days or 1
        months_diff = (date.today().year - first_service_order.service_date.year) * 12 + (date.today().month - first_service_order.service_date.month) or 1
        
        avg_per_day = round(total_service_orders / days_diff, 1)
        avg_per_month = round(total_service_orders / months_diff, 1)

    # Best Contractor & Best FOC Avg Day
    best_contractor = "N/A"
    best_foc_avg_day = 0
    
    top_contractor = ServiceOrder.objects.values('contractor__company').annotate(
        total_installations=Count('id')
    ).order_by('-total_installations').first()

    if top_contractor:
        best_contractor = top_contractor['contractor__company']
        if first_service_order:
             best_foc_avg_day = round(top_contractor['total_installations'] / days_diff, 1)

    # Billable Stock Estimate
    total_billable_stock = 0
    billable_materials = InventoryMaterial.objects.filter(is_billable=True, is_active=True)
    for b_mat in billable_materials:
        total_billable_stock += b_mat.stock()

    stock_estimate_days = "N/A"
    if avg_per_day > 0 and total_billable_stock > 0:
        stock_estimate_days = round(float(total_billable_stock) / float(avg_per_day))

    context['avg_per_day'] = avg_per_day
    context['avg_per_month'] = avg_per_month
    context['best_contractor'] = best_contractor
    context['best_foc_avg_day'] = best_foc_avg_day
    context['stock_estimate_days'] = stock_estimate_days
    
    return render(request, 'ssml/index.html', context)


@login_required
def materials(request):
    page = {
        'title': 'Materials',
        'page': 'materials',
        'page_title': 'Materials',
        'page_description': 'Materials',
        'nav':True,
        'last_material': InventoryMaterial.objects.last()
    }

    sr_opt = ""
    for rt in Service.objects.all().order_by('name'):
        sr_opt += f"<option value='{rt.id}'>{rt.name} - {rt.rate}</option>"
    context = {
        'page': page,
        'next_barcode': f"MT0{InventoryMaterial.objects.filter(is_issue=False).last().id if InventoryMaterial.objects.filter(is_issue=False).exists() else 0 + 1}",
        'service_rates':sr_opt,
        'services':ServiceType.objects.all().order_by('name')
        
    }
    return render(request, 'ssml/materials.html', context)

@login_required
def grn(request):
    if Grn.objects.count() == 0:
        return redirect('grn_add')
    else:
        last_grn = Grn.objects.last()
        last_grn_no = last_grn.grn_no
        last_grn_date = last_grn.grn_date
        last_grn_remarks = last_grn.remarks
        last_grn_created_by = last_grn.created_by
        last_grn_total_amount = last_grn.total_amount
        last_grn_total_qty = last_grn.total_qty
    page = {
        'title': 'GRN',
        'page': 'grn',
        'page_title': 'GRN',
        'page_description': 'GRN',
        'nav':True
    }
    context = {
        'page': page,
        'last_grn': last_grn,
        'last_grn_no': last_grn_no,
        'last_grn_date': last_grn_date,
        'last_grn_remarks': last_grn_remarks,
        'last_grn_created_by': last_grn_created_by,
        'last_grn_total_amount': last_grn_total_amount,
        'last_grn_total_qty': last_grn_total_qty,
        'last_grn_transactions': GrnTransaction.objects.filter(grn_id=last_grn.pk),
        'last_grn_next_row': last_grn.next_row(),
        'last_grn_prev_row': last_grn.prev_row(),
        'last_grn_status': last_grn.status()
    }
    return render(request, 'ssml/grn.html', context)

@login_required
def issue(request):
    if Issue.objects.count() == 0:
        return redirect('issue_add')
    else:
        last_issue = Issue.objects.last()
        last_issue_no = last_issue.issue_no
        last_issue_date = last_issue.issue_date
        last_issue_remarks = last_issue.remarks
    page = {
        'title': 'Issue',
        'page': 'issue',
        'page_title': 'Issue',
        'page_description': 'Issue',
        'nav':True
    }
    context = {
        'page': page,
        'last_issue': last_issue,
        'last_issue_no': last_issue_no,
        'last_issue_date': last_issue_date,
        'last_issue_remarks': last_issue_remarks,
        'last_issue_transactions': IssueTransaction.objects.filter(issue_id=last_issue.pk),
        'last_issue_next_row': last_issue.next_row(),
        'last_issue_prev_row': last_issue.prev_row(),
        'last_issue_status': last_issue.status(),
        'searchButton':'search_issue_by_issue_no'
    }
    return render(request, 'ssml/issue.html', context)

@login_required
def issue_add(request):
    page = {
        'title': 'Add Issue',
        'page': 'issue_add',
        'page_title': 'Add Issue',
        'page_description': 'Add Issue',
        'nav':True
    }
    context = {
        'page': page,
        'issue_types': Issue.issue_type_choices
    }
    return render(request, 'ssml/issue_add.html', context)

@login_required
def grn_add(request):
    page = {
        'title': 'Add GRN',
        'page': 'grn_add',
        'page_title': 'Add GRN',
        'page_description': 'Add GRN',
        'nav':True,

    }
    context = {
        'page': page,
        'locations': Location.objects.all().order_by('loc_name')
        
    }   
    return render(request, 'ssml/grn_add.html', context)

@login_required
def grn_edit(request, id):
    page = {
        'title': 'Edit GRN',
        'page': 'grn_edit',
        'page_title': 'Edit GRN',
        'page_description': 'Edit GRN',
        'nav':True
    }
    context = {
        'page': page,
        'grn': Grn.objects.get(id=id),
        'grn_transactions': GrnTransaction.objects.filter(grn_id=id),
        'nav':True,
        'suppliers': Supplier.objects.all(),
        'grn_date_to_html': Grn.objects.get(id=id).grn_date.strftime('%Y-%m-%d')
    }
    return render(request, 'ssml/grn_edit.html', context)

@login_required
def upload_image(request):
    if request.method == 'POST':
        id = request.POST.get('id')
        image = request.FILES.get('image')
        material = InventoryMaterial.objects.get(id=id)
        material.image = image
        material.save()
        return redirect('materials')
    return redirect('materials')

@login_required
def issue_edit(request, id):
    page = {
        'title': 'Edit Issue',
        'page': 'issue_edit',
        'page_title': 'Edit Issue',
        'page_description': 'Edit Issue',
        'nav':True
    }
    context = {
        'page': page,
        'issue': Issue.objects.get(id=id),
        'issue_transactions': IssueTransaction.objects.filter(issue_id=id),
        'contractors': Contractor.objects.all(),
        'issue_date_to_html': Issue.objects.get(id=id).issue_date.strftime('%Y-%m-%d'),
        'issue_types': Issue.issue_type_choices
    }
    return render(request, 'ssml/issue_edit.html', context)

@login_required
def plots(request):
    page = {
        'title': 'Plots',
        'page': 'plots',
        'page_title': 'Plots',
        'page_description': 'Plots',
        'nav':True
    }
    context = {
        'page': page
    }
    return render(request, 'ssml/plots.html', context)


@login_required
def service_orders(request):
    # ServiceOrder.objects.all()
    if(ServiceOrder.objects.all().count() < 1):
        return redirect('service_order_new')
    
    opts = ""
    for st in ServiceType.objects.all():
        opts += f"<option value='{st.id}'>{st.name}</option>"
    page = {
        'title': 'Service Order',
        'page': 'service_order',
        'page_title': 'Service Order',
        'page_description': 'Service Order',
        'nav':True,
        
    }
    
    context = {
        
        'page': page,
        'contractors': Contractor.objects.all(),
        'plots': Plot.objects.all(),
        'service_types': {
            'water': 'Water',
            'electricity': 'Electricity',
            'sewerage': 'Sewerage',
            'gas': 'Gas',
            'telecom': 'Telecom'
        },
        'last_service_order': ServiceOrder.objects.last(),
        'searchButton':'search_service_by_meter',
        'service_ops':opts
    }
    return render(request, 'ssml/service_order.html', context)


@login_required
def services(request):
    page = {
        'title': 'Services Rates',
        'page': 'services',
        'page_title': 'Service Rates',
        'page_description': 'Services',
        'nav':True
    }
    context = {
        'page': page
    }
    return render(request, 'ssml/services_rates.html', context)

@login_required
def contractors(request):
    page = {
        'title': 'Contractors',
        'page': 'contractors',
        'page_title': 'Contractors',
        'page_description': 'Contractors',
        'nav':True
    }
    context = {
        'page': page,
        'contractors': Contractor.objects.all(),
        'last_contractor': Contractor.objects.last()
    }
    return render(request, 'ssml/contractors.html', context)


@login_required
def contractor_list(request):
    page = {
        'title': 'Contractor List',
        'page': 'contractor_list',
        'page_title': 'Contractor List',
        'page_description': 'Contractor List',
        'nav':True
    }
    context = {
        'page': page,
        'contractors': Contractor.objects.filter(is_installer=True).order_by('company'),
        
    }
    return render(request, 'ssml/contractor_list.html', context)

@login_required
def service_order_new(request):
    
    page = {
        'title': 'New Service Order',
        'page': 'service_order_new',
        'page_title': 'New Service Order',
        'page_description': 'New Service Order',
        'nav':True,
        
    }
    context = {
        'page': page,
        'contractors': Contractor.objects.all(),
        'service_types': ServiceType.objects.all(),
        'issue_materials':InventoryMaterial.objects.filter(is_issue=True).order_by('name')
    }
    return render(request, 'ssml/service_order_new.html', context)


@login_required
def redeem(request):
    if Reedem.objects.all().count() < 1:
        return redirect('new_redeem')
    
    last_entry = Reedem.objects.all().last()
    page = {
        'title': 'Redeem',
        'page': 'service_order_new',
        'page_title': 'New Service Order',
        'page_description': 'New Service Order',
        'nav':True,
        
    }
     
    context = {
         'page':page,
         'last_entry':last_entry
     }
    
    return render(request, 'ssml/redeem.html', context)

@login_required
def new_redemption(request):
    page = {
        'title': 'New Redeem',
        'page': 'service_order_new',
        'page_title': 'New Service Order',
        'page_description': 'New Service Order',
        'nav':True,
        
    }
     
    context = {
         'page':page,
         'contractors':Contractor.objects.all().order_by('company')
     }
    
    return render(request, 'ssml/new_redeem.html', context)

@login_required
def meters(request):
    page = {
        'title':"Meters",
        'nav':True
    }

    # delete all return materials in issued
    #MaterialOrderItem.objects.filter(material__is_return=True,material_type='is').delete()

    context = {
         'page':page,
         'meters':Meter.objects.all()[:20]
     }
    
    return render(request, 'ssml/meters.html', context)

@login_required
def retired_meters(request):
    page = {
        'title':"Retired Meters",
        'nav':True
    }

    # delete all return materials in issued
    #RetiredMetersBox.objects.all().delete()

    context = {
         'page':page,
         "last_pk":RetiredMetersBox.objects.all().last().pk if RetiredMetersBox.objects.all().count() > 0 else 0
     }
    
    return render(request, 'ssml/retired-meters.html', context)


@login_required
def contractor_errors(request):
    page = {
        'title': 'Contractor Errors',
        'page': 'contractor_errors',
        'page_title': 'Contractor Errors',
        'page_description': 'Contractor Errors',
        'nav':True
    }
    context = {
        'page': page,
        'contractor_errors': ContractorError.objects.filter(is_cleared=False).order_by('-created_at'),
        'contractors': Contractor.objects.all().order_by('company'),
        'locations':Location.objects.all().order_by('loc_id')
    }
    return render(request, 'ssml/contractor_errors.html', context)

@login_required
def save_contractor_error(request):
    if request.method == 'POST':
        meter_no = request.POST.get('meter')
        location = Location.objects.get(pk=request.POST.get('mt_location'))

        contractor = Contractor.objects.get(pk=request.POST.get('contractor'))

    # add or get meter
        if not Meter.objects.filter(meter_no=meter_no).exists():
            Meter.objects.create(
                meter_no=meter_no,
                contractor=Contractor.objects.get(pk=request.POST.get('contractor')),
                created_by=request.user,
                location=location
            )


        form = ContractorErrorForm(request.POST)
        if form.is_valid():
            error = form.save()
            # make sms 
            Sms.objects.create(
                api=SmsApi.objects.get(is_default=True),
                to=contractor.phone,
                message=f"Error reported for meter {meter_no}. Issue: {error.description}. Please check and resolve before coming for new materials \nPay N Smile."
            )
            return redirect('contractor_errors')
        else:
            return HttpResponse(form.errors)
    return redirect('contractor_errors')


@login_required
def accounts(request):
    if not request.user.is_superuser:
        return HttpResponse("Invalid Access")
    page = {
        'title': 'Accounts',
        'page': 'accounts',
        'page_title': 'Accounts',
        'page_description': 'Accounts',
        'nav':True
    }
    context = {
        'page': page
    }
    return render(request, 'ssml/accounts.html', context)



@login_required
def servive_type(request,id):
    service = ServiceType.objects.get(id=id)
    page = {
        'title': 'Service Type',
        'page': 'service_type',
        'page_title': 'Service Type',
        'page_description': 'Service Type',
        'nav':True
    }
    context = {
        'page': page,
        'service':service,
        'service_rates':Service.objects.all().order_by('name'),
        'my_rates':ServiceTypeServices.objects.filter(service_type=service),
        'id':id,
        'required_returns':RequiredReturn.objects.filter(service_type=service)
    }

    return render(request,'ssml/service-type.html',context=context)

@login_required
def add_service_to_type(request):
    if request.method == 'POST':
        selected_services = request.POST.getlist('service[]')
        s_type = request.POST['s_type']
        for service in selected_services:
            service_rate = Service.objects.get(id=service)
            try:
                ServiceTypeServices(
                    service_type_id=s_type,
                    service = service_rate
                ).save()
            except Exception as e:
                pass
            # print(service_rate.name,service_rate.rate)
        # You can now use this list however you want, e.g., save to DB

    

    return redirect(request.META.get('HTTP_REFERER', '/'))

@csrf_exempt
@login_required
def upload_service_order(request):
    if request.method == 'POST':

        # Meter.objects.all().delete()
        # ServiceOrder.objects.all().delete()

        # for tp in ServiceType.objects.all():
        #     if ServiceOrder.objects.filter(service_type=tp) == 0:
        #         tp.delete()

        if 'excel_file' not in request.FILES:
            return HttpResponseBadRequest("No file uploaded.")
        
        import openpyxl
        excel_file = request.FILES['excel_file']
        wb = openpyxl.load_workbook(excel_file)
        sheet = wb.active  # or wb['SheetName'] if you know it
        # service_id = request.POST['service']
        # service = ServiceType.objects.get(pk=service_id)
        # service_name = service.name

        loc_id = request.POST['loc_id']
        loc = Location.objects.get(loc_id=loc_id)

        headers = [cell.value for cell in sheet[1]]

        
        sample_data = []

        # service_rates = ServiceTypeServices.objects.filter(service_type=service)

        cts = 0
      
        r_count = 1
        r_len = sheet.max_row - 1 
        for row in sheet.iter_rows(min_row=2, values_only=True):
            print("#" * 20)
            cts += 1
            row_dict = dict(zip(headers, row))
            print(row_dict)
            customer = row_dict['CUSTOMER NAME']
            customer_phone = row_dict['CUSTOMER PHONE']
            contractor_code = row_dict['CONTRACTOR CODE']
            if not Contractor.objects.filter(code=contractor_code).exists():
                Contractor.objects.create(
                    code=contractor_code,
                    company=f"{contractor_code} created from job upload",
                    created_by=request.user,
                    email=f"{contractor_code}@{contractor_code}.com",
                    gh_card_no=contractor_code,
                    owner=contractor_code,
                    phone=contractor_code,

                ).save()
            contractor = Contractor.objects.get(code=contractor_code)
            dt = row_dict['DATE COMPLETED'] if row_dict.get('DATE COMPLETED')  else row_dict['DATE RESOLVED']
            from datetime import datetime
            resolved_on = datetime.strptime(dt, "%d/%m/%Y %H:%M")
            # print(resolved_on)
            meter_no = row_dict['MFG Serial Number']
            ip_address = row_dict['IP Address']

            order_status = row_dict['PREPAID SYNC STATUS']
            address = row_dict['DIGITAL ADDRESS']
            phase = row_dict['REQUESTED METER PHASE'].lower() if row_dict.get('REQUESTED METER PHASE') else False
            if not phase:
                phase = row_dict['METER PHASE'].lower() if row_dict.get('METER PHASE') else '1'

            # create meter
            print('FILE PHASE:',phase)
            first_char = phase[0] if len(str(phase)) > 0 else 1
            print("FiRST CHAR",first_char)
            phase_by_desc = Phase.objects.filter(number=first_char).order_by('id').first()
            if not phase_by_desc:
                phase_by_desc = Phase.objects.filter(number=1).order_by('id').first()
            if not Meter.objects.filter(meter_no=meter_no).exists():
                

                Meter.objects.create(
                    meter_no=meter_no,
                    ip_address=ip_address,
                    location=loc,
                    created_by=request.user,
                    installation_address=address,
                    phase=phase,
                    contractor=contractor,
                    created_at=resolved_on,
                    updated_at=resolved_on,
                    is_issued=True,
                    linked_phase=phase_by_desc
                )

                phase =  'Unknown'
                print("Phase created for", meter_no, "to", phase)

            else:
                # update phase
                meter = Meter.objects.get(meter_no=meter_no)
                meter.linked_phase = phase_by_desc
                meter.save()
                phase =  'Unknown'
                print("Phase updated to", phase)

            old_meter = row_dict['OLD METER NUMBER'] if row_dict.get('OLD METER NUMBER') else meter_no
            spn = row_dict['SERVICE POINT NUMBER'] if row_dict.get('SERVICE POINT NUMBER') else row_dict.get('SERVICE POINT NUMBER')
            geo_code = row_dict['GEOCODE'] if row_dict.get('GEOCODE') else meter_no
            service_order_type = row_dict['SERVICE ORDER TYPE']
            re_routing = row_dict["RE-ROUTING TYPE"] if row_dict.get('RE-ROUTING TYPE') else 'Without Rerouting'
            installation_type_desc = row_dict['INSTALLATION TYPE'] if row_dict.get('INSTALLATION TYPE') else 'UNKNOWN'
            
            routing = False
            
            if re_routing == "Without Rerouting":
                routing = False
            else:
                routing = True

            if service_order_type == 'Replacement':
                if routing:
                    installation_type_desc = 'Rerouting'
                else:
                    installation_type_desc = service_order_type

            
            if not InstallationType.objects.filter(name=installation_type_desc).exists():
                InstallationType.objects.create(
                    name=installation_type_desc,
                    description=installation_type_desc,
                    created_by=request.user
                )

            installation_type = InstallationType.objects.get(name=installation_type_desc)
            if not ServiceType.objects.filter(name=service_order_type).exists():
                ServiceType.objects.create(
                    name=service_order_type,
                    description=service_order_type,
                    created_by=request.user,
                )

            service = ServiceType.objects.get(name=service_order_type)
            service_rates = ServiceTypeServices.objects.filter(service_type=service)

            ServiceOrder.objects.filter(new_meter=meter_no).delete()
            xi = [service_order_type,customer,customer_phone,contractor.company,resolved_on,meter_no,ip_address]
            
            # print(xi)

            # get materials
            service_charge = 0

            #if order_status == 'Completed': 
            if True:
                hd = [service_order_type,customer,customer_phone,contractor.company,resolved_on,meter_no,ip_address]

                
                print(r_count , "/" , r_len)
                print("SPN",spn)
                print("SERVICE TYPE",service.name)
                print("ROUTING",routing)
                print("NEW METER",meter_no)
                print("PHASE",phase)
                print("INSTALLATIO TYPE",installation_type_desc)

                print("#" * 20)

                r_count += 1
                

                if ServiceOrder.objects.filter(old_meter_no=old_meter).exists():
                    # # send sms
                    # Sms.objects.create(
                    #     api=SmsApi.objects.get(is_default=True),
                    #     to=contractor.phone,
                    #     message=f"There is a duplicate old meter {meter_no}:{old_meter}"
                    # )
                    # # send message to soomon
                    # Sms.objects.create(
                    #     api=SmsApi.objects.get(is_default=True),
                    #     to="0546310011",
                    #     message=f"There is a duplicate old meter {meter_no}:{old_meter}"
                    # )
                    # Sms.objects.create(
                    #     api=SmsApi.objects.get(is_default=True),
                    #     to='0543700095',
                    #     message=f"There is a duplicate old meter {meter_no}:{old_meter}"
                    # )
                    
                    old_meter = f"dup_{old_meter}{make_md5_hash(meter_no)}"
                                  
                    # create
                try:
                    ServiceOrder(
                            service_type= service,
                            service_date = resolved_on,
                            contractor=contractor,
                            plot = "",
                            geo_code = geo_code,
                            customer = customer,
                            customer_no = customer_phone,
                            old_meter_no = old_meter,
                            new_meter=meter_no,
                            status=order_status,
                            created_by=request.user,
                            location=loc,
                            spn=spn,
                            is_routing = routing,
                            gps_code=address,
                            phase=phase,
                            installation_type=installation_type
                        ).save()
                    # print("Service Created")
                except Exception as e:
                    # update type
                    print("Error Creating Service :",str(e))
                    print("Error: Mark End")
                    ServiceOrder.objects.filter(new_meter=meter_no).update(
                        service_type= service,
                            service_date = resolved_on,
                            contractor=contractor,
                            plot = "",
                            geo_code = geo_code,
                            customer = customer,
                            customer_no = customer_phone,
                            old_meter_no = old_meter,
                            new_meter=meter_no,
                            status=order_status,
                            created_by=request.user,
                            location=loc,
                            spn=spn,
                            is_routing = routing,
                            phase=phase,
                            gps_code=address,
                            installation_type=installation_type
                        )
                    # print(e)
                # print(meter_no)
                met_service = ServiceOrder.objects.get(new_meter=meter_no)
            

                # # print(hd)
                # # print('RATES')
                rate_message = ""
                total_rate = 0
                for rate in service_rates:
                    rx = rate.service
                    name = rate.service.name
                    rt = rate.service.rate
                    total_rate += rt
                    # rate_message += f"{name},1,{rt},{rt*1}\n"

                    if ServiceOrderItem.objects.filter(service_order=met_service,service=rate.service).exists:
                        ServiceOrderItem.objects.filter(service_order=met_service,service=rate.service).delete()
                    
                        # insert
                    ServiceOrderItem(
                            service_order=met_service,service=rx,
                            quantity=1,rate=rt,amount=Decimal(rt)*Decimal(1)

                        ).save()
                    # # print(name,rt)    
                # print("Materials")       
                materials_message = ''
                for material in InventoryMaterial.objects.all().order_by('name'):
                    qty = row_dict.get(material.name,0)
                    # add material or update
                    MaterialOrderItem.objects.filter(service_order=met_service,material=material).delete()
                    

                    if qty > 0:
                        # # print("FISH",material.name,qty)
                        materials_message += f"{material.name} | {qty}\n"

                        
                        MaterialOrderItem(
                                service_order=met_service,material=material,quantity=qty,rate=0,amount=0
                            ).save()
                        
                        # get service rates
                        other_rates = ServiceMaterialRates.objects.filter(material__barcode=material.barcode)
                        # # print(other_rates.count(),"COUNTED")
                        if other_rates.count() > 0:
                            extra_rate = ServiceMaterialRates.objects.get(material__barcode=material.barcode)
                            if qty > extra_rate.break_point :
                                # # print("GREATER")
                                rate = extra_rate.service.rate
                                name = extra_rate.service.name
                                total_rate += extra_rate.service.rate
                                # rate_message += f"{name},1,{rt},{rt*1}\n"
                            else:
                                pass
                                # # print("NOT GREATER")
                        
                        # # print(meter_no, material.name,qty)
                    else:
                        pass
                        # print("Material Not Found Here")
                # default issues    
                MaterialOrderItem.objects.filter(service_order=met_service)    
                for mat in ServiceMaterials.objects.filter(service=service,phase=phase_by_desc):
                    # print(mat.material.name,mat.qty)
                    try:
                        MaterialOrderItem.objects.create(
                                    service_order=met_service,material=mat.material,quantity=mat.qty,rate=0,amount=0
                                )
                        print(f"{mat.material.name} - {mat.qty} Added")
                    except Exception as e:
                        pass
                        print(e)
                        
                    
                # update total amount
                met_service.total_amount = ServiceOrder.objects.get(new_meter=meter_no).total_amount()



            # # print(f'###### {contractor.company} ##### {meter_no}')
            # # print("MATERIALS")
            # # print(materials_message)
            # # print("SERVICE RATES")
            # # print(rate_message)

            # # print(f'###### total ##### {total_rate}')
            # # print('\n')
            sample_data.append(row_dict)

        # print(cts, service_order_type, "Added")

        return redirect(request.META.get('HTTP_REFERER', '/'))



    else:
        return redirect(request.META.get('HTTP_REFERER', '/'))


@csrf_exempt
@login_required
def sync_retired_meter(request):
    from datetime import datetime
    if request.method == 'POST':
        if 'excel_file' not in request.FILES:
            return HttpResponseBadRequest("No file uploaded.")

        import openpyxl

        excel_file = request.FILES['excel_file']
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        sheet = wb.active  # ✅ FIXED

        box_no = request.POST.get('boxx_no')
        loc_id = request.POST.get('loc')

        if not loc_id:
            return HttpResponseBadRequest("Location is required.")

        try:
            location = Location.objects.get(loc_id=loc_id)
        except Location.DoesNotExist:
            return HttpResponseBadRequest("Invalid location.")

        print(request.POST)

        # delete existing
        RetiredMetersBox.objects.filter(
            box_no=box_no,
            location=location,
        ).delete()



        # create new
        box = RetiredMetersBox.objects.create(
            box_no=box_no,
            location=location,
            created_by=request.user,
        )

        rows = list(sheet.iter_rows(values_only=True))

        if not rows:
            return HttpResponseBadRequest("Excel file is empty.")

        headers = rows[0]

        if not any(headers):
            return HttpResponseBadRequest("Header row is empty.")

        for row in rows[1:]:
            if not any(row):
                continue

            obj = dict(zip(headers, row))
            sn = obj.get('SN')
            spn = obj.get('SERVICE POINT NUMBER')
            old_meter_no = obj.get('OLD METER NUMBER')
            if old_meter_no is None:
                old_meter_no = spn

            # print(old_meter_no)
            final_reading = 0
            rem_wattage = 0
            rem_cedis = 0
            make_year = 'UNKNWONM'
            manufacturere = 'UNKNOWN'
            phase = ''
            rating = 0
            raw_date = obj.get('DATE APPROVED')
            phase = obj.get('REQUESTED METER PHASE')

            # print("RAW DATE", raw_date)

            date_removed = None

            if raw_date:
                try:
                    if isinstance(raw_date, datetime):
                        # Already a datetime → just extract date
                        date_removed = raw_date.date()
                    else:
                        # It's a string → parse it
                        date_removed = datetime.strptime(raw_date, "%d/%m/%Y %H:%M").date()
                except Exception as e:
                    print("Date parse error:", raw_date, e)

            reason = ''
            foc = Contractor.objects.get(code=obj.get('CONTRACTOR CODE'))
            gps_address = obj.get('DIGITAL ADDRESS')

            RetiredMetersTransactions.objects.filter(spn=spn).delete()

            spn = str(int(float(spn)))
            old_meter_no = str(int(float(old_meter_no)))
            service_order = ServiceOrder.objects.filter(spn=spn)
            if service_order:
                sd = service_order.last()
                date_removed = sd.service_date
                print(f"{spn} service date overwrite")
            else:
                print(f"{spn} service date not overwrite")

            RetiredMetersTransactions.objects.create(
                box=box,
                sn=sn,
                spn=spn,
                old_meter_no=old_meter_no,
                final_readings=final_reading,
                rem_wattage=rem_wattage,
                rem_cedis=rem_cedis,
                make_year=make_year,
                manufacturere=manufacturere,
                phase=phase,
                rating=rating,
                date_removed=date_removed,
                reason=reason,
                foc=foc,
                gps_address=gps_address,
            )


            if ServiceOrder.objects.filter(spn=spn).exists():
                ct = ServiceOrder.objects.filter(spn=spn).count()
                date_removed = ServiceOrder.objects.filter(spn=spn).last().service_date
                ServiceOrder.objects.filter(spn=spn).update(
                    is_boxed=True,
                    box_no=box_no,
                    final_readings=final_reading

                )

            else:
                from datetime import datetime, date

                # ... inside your function ...
                dm = date_removed


                if dm:
                    if isinstance(dm, (datetime, date)):
                        # It's already a date/datetime object, just ensure it's a date
                        if isinstance(dm, datetime):
                            date_removed = dm.date()
                        else:
                            date_removed = dm
                    elif isinstance(dm, str):
                        # It's a string, so we proceed with parsing
                        try:
                            date_removed = datetime.strptime(dm, '%d/%m/%Y %H:%M').date()
                        except ValueError:
                            try:
                                date_removed = datetime.strptime(dm, '%m/%d/%Y').date()
                            except ValueError:
                                try:
                                    date_removed = datetime.strptime(dm, '%m/%d/%Y %H:%M').date()
                                except ValueError:
                                    try:
                                        date_removed = datetime.strptime(dm, '%d/%m/%Y').date()
                                    except Exception as e:
                                        date_removed = None
                    else:
                        date_removed = None

        box.file = excel_file
        box.save()  # ✅ you forgot this

        return JsonResponse({"status_code": 200, "message": "sync_ret_meter"})
@csrf_exempt
@login_required
def add_material_rate(request):
    if request.method == 'POST':
        form = request.POST
        mat_id = form.get('mat_id')
        break_point = form.get('break_point')
        service_rate_id = form.get('service_rate')
        material = InventoryMaterial.objects.get(id=mat_id)
        rate = Service.objects.get(id=service_rate_id)
        try:
            ServiceMaterialRates(
                service=rate,material=material,break_point=break_point
            ).save()
        except Exception as e:
            pass

        ## add to model

        # print(form)
    return redirect(request.META.get('HTTP_REFERER', '/'))


def delete_service_rate(request,id):
    ServiceMaterialRates.objects.filter(id=id).delete()

    return redirect(request.META.get('HTTP_REFERER', '/'))
def delete_type_service_rate(request,id):
    ServiceTypeServices.objects.filter(id=id).delete()

    return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required
def invoice(request):
    # FocInvoiceHd.objects.all().delete()
    
    last_entry = FocInvoiceHd.objects.all().last().entry_no if FocInvoiceHd.objects.all().count() > 0 else None
    page = {
        'title': 'FOC Invoice',
        'page': 'contractor_invoice',
        'page_title': 'Contractor Invoice',
        'page_description': 'Service Type',
        'nav':True
    }
    context = {
        'page': page,
        'last_entry':last_entry
    }

    return render(request,'ssml/contractor-invoice.html',context=context)
@login_required
def invoice_new(request):
    page = {
        'title': 'NEW Contractor Invoice',
        'page': 'contractor_invoice',
        'page_title': 'Contractor Invoice',
        'page_description': 'Service Type',
        'nav':True
    }
    context = {
        'page': page,
        'contractors':Contractor.objects.all().order_by('company')
    }

    return render(request,'ssml/contractor-invoice-new.html',context=context)
@login_required
def invoice_edit(request, pk):
    invoice = InvoiceHD.objects.get(pk=pk)
    page = {
        'title': 'EDIT Contractor Invoice',
        'page': 'contractor_invoice',
        'page_title': 'Contractor Invoice',
        'page_description': 'Service Type',
        'nav': True
    }
    context = {
        'page': page,
        'contractors': Contractor.objects.all().order_by('company'),
        'invoice': invoice
    }
    return render(request, 'ssml/contractor-invoice-edit.html', context=context)
@login_required
def location_master(request):
    page = {
        'title': 'Location Master',
        'page': 'ssml_location_master',
        'page_title': 'Location Master',
        'page_description': 'Location Master',
        'nav':True
    }
    context = {
        'page': page
    }

    return render(request,'ssml/location-master.html',context=context)

@login_required()
def transfer(request):
    # TransferHd.objects.all().delete()
    if TransferHd.objects.all().count() == 0:
        return redirect('ssml_add_transfer')
    page = {
        'title': 'Transfer',
        'page': 'transfer',
        'page_title': 'Transfer',
        'page_description': 'Transfer',
        'nav':True,
        
    }

    if request.GET.get('entry'):
        if TransferHd.objects.filter(entry_no=request.GET.get('entry')).count() > 0:
            last_entry = TransferHd.objects.filter(entry_no=request.GET.get('entry')).last().id
        else:
            last_entry = TransferHd.objects.all().last().id
    else:
        last_entry = TransferHd.objects.all().last().id
    context = {
        'page': page,
        'last_entry':last_entry,
        'nav':True
    }

    return render(request,'ssml/inventory/transfer.html',context=context)

@login_required()
def add_transfer(request):
    page = {
        'title': 'Add Transfer',
        'nav':True
    }

    context = {
        'page': page,
        'locations': Location.objects.all().order_by('loc_name'),
    }

    return render(request,'ssml/inventory/transfer_add.html',context=context)


    # INSERT_YOUR_CODE
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import FinancialEvidence ,Expense # Assuming these models exist

@login_required()
@csrf_exempt
def financial_evidence(request):
    if request.method == 'POST':
        transaction_id = request.POST.get('transaction_id')
        title = request.POST.get('title')
        file = request.FILES.get('file')

        if not (transaction_id and title and file):
            return HttpResponse(title)
            return JsonResponse({'status': False, 'message': 'Missing required fields.'}, status=400)

        try:
            transaction = Expense.objects.get(id=transaction_id)
        except Expense.DoesNotExist:
            return JsonResponse({'status': False, 'message': 'Transaction not found.'}, status=404)

        evidence = FinancialEvidence.objects.create(
            transaction=transaction,
            title=title,
            file=file,
            uploaded_by=request.user
        )
        from django.shortcuts import redirect
        return redirect(request.META.get('HTTP_REFERER', '/'))

    else:
        return JsonResponse({'status': True, 'message': 'Invalid Method',"":""})
    


        # INSERT_YOUR_CODE
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required()
def request_expense(request):
    page = {
        'title': 'Request Expense',
        'nav': False
    }
    context = {
        'page': page,
    }
    # INSERT_YOUR_CODE
    # Pass category_choices in context
    from .models import Expense  # Assuming Expense model has category choices

    if hasattr(Expense, 'category_choices'):
        category_choices = Expense.category_choices
    else:
        category_choices = []

    context['category_choices'] = category_choices
    return render(request, 'ssml/accounts-req-expense.html', context=context)




from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone


@login_required()
def save_expense_request(request):
    if request.method == "POST":
        from decimal import Decimal, InvalidOperation

        # Get data from POST
        category = request.POST.get('category')
        amount = request.POST.get('amount')
        date = request.POST.get('date')
        reference = request.POST.get('reference', '')
        description = request.POST.get('description', '')
        evidence_file = request.FILES.get('evidence')

        # Validate required fields
        if not (category and amount and date):
            return JsonResponse({'status': False, 'message': 'Missing required fields.'}, status=400)

        # Validate amount
        try:
            amount = Decimal(amount) * -1
        except (InvalidOperation, TypeError):
            return JsonResponse({'status': False, 'message': 'Invalid amount.'}, status=400)

        # Save Expense (direction is always 'out' for requests, transaction_type is 'cash' by default)
        expense = Expense.objects.create(
            direction='out',
            date=date,
            category=category,
            transaction_type='cash',
            amount=amount,
            reference=reference,
            description=description,
            created_by=request.user
        )

        # Save evidence if provided
        file_name = ""
        if evidence_file:
            from .models import FinancialEvidence
            FinancialEvidence.objects.create(
                transaction=expense,
                title="Evidence",
                file=evidence_file,
                uploaded_by=request.user
            )
        
            file_name = FinancialEvidence.objects.last().file.url
        # INSERT_YOUR_CODE
        # Prepare email subject and body for notification (not sending, just variables)
        email_subject = f"Expense Request Submitted by {request.user.get_full_name() or request.user.username}"
        email_body = f"""
        <div style="padding:0;margin:0;">
            <div style="max-width:420px;margin:0 auto;background:#fff;border-radius:6px;box-shadow:0 2px 8px #0001;padding:40px 30px 30px 30px;position:relative;top:40px;">
                <h1 style="text-align:center;font-size:2.2em;letter-spacing:2px;margin-bottom:18px;font-family:sans-serif;">Expense Request</h1>
                <p style="font-size:1.1em;color:#222;margin-bottom:24px;font-family:sans-serif;">
                    An expense request has been submitted. Please review the details below.
                </p>
                <div style="background:#f4f8fb;border-radius:5px;padding:18px 20px 10px 20px;margin-bottom:24px;alight-text:left">
                    <p style="margin:0 0 10px 0;font-family:sans-serif;"><b>Submitted by:</b> {request.user.get_full_name() or request.user.username}</p>
                    <p style="margin:0 0 10px 0;font-family:sans-serif;"><b>Category:</b> {category}</p>
                    <p style="margin:0 0 10px 0;font-family:sans-serif;"><b>Amount:</b> {amount}</p>
                    <p style="margin:0 0 10px 0;font-family:sans-serif;"><b>Date:</b> {date}</p>
                    <p style="margin:0 0 10px 0;font-family:sans-serif;"><b>Reference:</b> {reference}</p>
                    <p style="margin:0 0 10px 0;font-family:sans-serif;"><b>Description:</b> {description}</p>
                    <p style="margin:0 0 0 0;font-family:sans-serif;"><b>Submitted at:</b> {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                
            </div>
            
        </div>
        """

        # que mail
        
        if MailSenders.objects.filter(address='solomon@snedaghana.com').exists():
            sender = MailSenders.objects.get(address='solomon@snedaghana.com')
        else:
            sender = MailSenders.objects.get(is_default=True)

        subject = email_subject
        mail = MailQueues(sender=sender, subject=subject, body=email_body,
                                      recipient='solomon@snedaghana.com',
                                      cc='uyinsolomon2@gmail.com,ajay@snedaghana.com,bharat@snedaghana.com',mail_key=make_md5_hash(f"{subject}{email_body}"))
        mail.save()
        
        if evidence_file:
            # INSERT_YOUR_CODE
            
            MailAttachments(mail=mail, attachment=file_name).save()

        
        # Redirect to accounts page or show success
        return HttpResponseRedirect(reverse('accounts'))

    # If not POST, redirect to request page
    return HttpResponseRedirect(reverse('request_expense'))

@csrf_exempt
@login_required
def approve_document(request):
    if request.method == 'POST':
        try:
            form = request.POST
            entry_no = form.get('entry_no')
            doc = form.get('doc')
            title = form.get('title')
            description = form.get('title')
            entry_no = form.get('entry_no')

            if doc == 'ssml_tr':
                document = TransferHd.objects.get(entry_no=entry_no)
                document.post()
                

            # upload file
            Documents.objects.create(
                title=title,
                file=request.FILES.get('file') if request.FILES else None,
                description=description,
                doc_type=doc,
                ref=entry_no
            )

            # INSERT_YOUR_CODE
            from django.http import JsonResponse
            return JsonResponse({'status_code': '200','message':"Document Approved"})
        
        except Exception as e:
            # INSERT_YOUR_CODE
            from django.http import JsonResponse
            return JsonResponse({'status_code': '500', 'message': str(e)})


def foc_portal(request):
    # Render the template into a response object
    response = render(request, 'ssml/foc-potal.html')

    # Check if 'stage' cookie exists
    if not request.COOKIES.get('stage'):
        # Set the cookie if it doesn't exist
        response.set_cookie('stage', 'auth', max_age=3600)  # expires in 1 hour

    return response


def my_company(request):
    stage = request.COOKIES.get('stage', None)
    if not stage:
        return redirect('ssml_foc_portal')

    foc_code = request.COOKIES.get('foc_id')
    # print(foc_code)
    foc = Contractor.objects.get(code=foc_code)
    page = {
        'title': 'My Company',
        'page': 'my_company',
        'stage': stage,
        'nav': True
    }
    context = {
        'page': page,
        'foc':foc
    }
    return render(request, 'ssml/foc/my-company.html', context)

@login_required
@csrf_exempt
def upload_contractor_docs(request):

    if request.method == 'POST':
        try:
            form = request.POST
            foc_id = form.get('pk')
            title = form.get('title')
            description = form.get('description')
            file = request.FILES.get('file')

            contractor = Contractor.objects.get(id=foc_id)
            ContractorDocuments.objects.create(
                contractor=contractor,
                title=title,
                file=file,
                description=description
            )

            return JsonResponse({'status_code': '200','message':"Document Uploaded"})
        except Exception as e:
            return JsonResponse({'status_code': '500', 'message': str(e)})
    return JsonResponse({'status_code': '500', 'message': "Invalid Method"})


def service_tools(request):
    page = {
        'title': 'Service Tools',
        'nav': True
    }
    context = {
        'page': page
    }
    return render(request, 'ssml/service/tools.html', context)

@login_required()
def petty_cash(request):
    # PettyCash.objects.all().delete()
    # Expense.objects.all().update(entry_no='')
    page = {
        'title': 'Petty Cash',
        'nav': True
    }

    context = {
        'page': page,
        'last_petty_cash_entry':PettyCash.objects.all().last().entry_no if PettyCash.objects.all().exists() else 'none'
    }

    return render(request, 'ssml/accounts/petty-cash.html', context)

@login_required()
def post_transfer(request, entry_no):
    page = {
        'title': 'Post Transfer',
        'nav': True
    }
    context = {
        'page': page,
        'entry_no': entry_no,
        'transfer': TransferHd.objects.get(entry_no=entry_no)
    }
    return render(request, 'ssml/inventory/transfer_post.html', context)

@login_required
@csrf_exempt
def ulbm(request):
    if request.method == 'POST':
        try:
            form = request.POST
            loc_id = form.get('loc_pk')
            boxing_file_link = form.get('boxing_file_link')
            file = request.FILES.get('auth_file')

            location = Location.objects.get(pk=loc_id)
            location.boxing_file_link = boxing_file_link
            location.boxing_auth_file = file
            location.save()

            return JsonResponse({'status_code': '200','message':"Document Uploaded"})
        except Exception as e:
            return JsonResponse({'status_code': '500', 'message': str(e)})
    return JsonResponse({'status_code': '500', 'message': "Invalid Method"})

@login_required
def cardex(request,barcode):
    page = {
        'title': 'Cardex',
        'nav': True
    }
    material = InventoryMaterial.objects.get(barcode=barcode)
    context = {
        'page': page,
        'product': InventoryMaterial.objects.get(barcode=barcode),
        'cardex': Cardex.objects.filter(material=material)
    }
    return render(request, 'ssml/cardex.html', context)


@login_required
@csrf_exempt
def import_expensis(request):
    # INSERT_YOUR_CODE
    from django.http import JsonResponse
    import openpyxl

    if request.method == "POST" and request.FILES.get('expensis_file'):
        expensis_file = request.FILES['expensis_file']
        try:
            wb = openpyxl.load_workbook(expensis_file, data_only=True)
            if "Expensis Log" not in wb.sheetnames:
                return JsonResponse({'status_code': '400', 'message': 'Sheet "Expensis Log" not found.'})
            sheet = wb["Expensis Log"]

            headers = [cell.value for cell in sheet[1]] 
            print("HEADER",headers)
            data = []
            for row in sheet.iter_rows(min_row=2,values_only=True):
                rowd = dict(zip(headers, row))
                if rowd['DATE']:
                    tran_date = rowd['DATE']
                    direction = rowd['DIRECION']
                    title = rowd['TITLE']
                    description = rowd['DESCRIPTION']
                    amount = rowd['ISSUED']
                    # li = [tran_date,direction,title,description,amount]
                    # print(li)
                    try:
                        Expense.objects.create(
                            direction=direction.lower(),
                            date=tran_date,
                            category='other',
                            transaction_type='other',
                            amount=amount,
                            reference=title,
                            description=description,
                            created_by=request.user

                        )



                        li = [tran_date,direction,title,description,amount]
                        print(li)
                    except Exception as e:
                        print(e)
                
            return JsonResponse({'status_code': '200', 'message': 'Success', 'data': data})
        except Exception as e:
            return JsonResponse({'status_code': '500', 'message': str(e)})
    else:
        return JsonResponse({'status_code': '400', 'message': 'No file uploaded or wrong method.'})

@login_required()
def phase_master(request):
    page = {
        'title':"Phase Master",
        'nav':True
    }

    # delete all return materials in issued
    #MaterialOrderItem.objects.filter(material__is_return=True,material_type='is').delete()
    unphased = Meter.objects.filter(linked_phase__isnull=True)
    context = {
         'page':page,
         'phases':Phase.objects.all(),
         'unphased_total':unphased.count(),
         'unphased':unphased
     }
    
    return render(request, 'ssml/meters/phase-master.html', context)

@login_required
def linked_models(request):
    page = {
        'title':"Linked Models",
        'nav':True
    }
    context = {
        'page':page,
        'linked_models':ServiceMaterials.objects.all()
    }
    return render(request, 'ssml/inventory/linked-models.html', context)

@login_required
def new_material_request_screen(request):
    
    page = {
        'title': "New Material Request",
        'nav': True
    }
    context = {
        'page': page,
        # 'form': MaterialRequestForm() # Assuming a form exists
    }
    return render(request, 'ssml/inventory/new-material-request.html', context)

@login_required
def material_request(request):
    if request.GET.get('entry_no'):
        request_no = request.GET.get('entry_no')
        
    else:
        if MaterialRequestHeader.objects.all().count() > 0:
            request_no = MaterialRequestHeader.objects.all().last().request_no
        else:
            return redirect('ssml_new_material_request')
    page = {
        'title': "Material Request",
        'nav': True
    }
    context = {
        'page': page,
        'request_no':request_n  
    }
    return render(request, 'ssml/inventory/material-request.html', context)

@csrf_exempt
@login_required
def import_shipment_file(request):
    if request.method == 'POST':
        file = request.FILES.get('shipment_file')
        if 'shipment_file' not in request.FILES:
            return HttpResponseBadRequest("No file uploaded.")

        print(request.POST)
        phase = Phase.objects.get(number=request.POST.get('phase'))
        
        excel_files = request.FILES.getlist('shipment_file')
        files_count = len(excel_files)
        fk = 1
        total_meters = 0
        for excel_file in excel_files:
        
            file_name = excel_file.name
            file_updates = 0
            file_creations = 0
            file_errors = []
            
            import openpyxl
            wb = openpyxl.load_workbook(excel_file)
            sheet = wb.active
            headers = [cell.value for cell in sheet[1]]
            all_rows_len = sheet.max_rorw - 1
            cans = 1
            for row in sheet.iter_rows(min_row=2,values_only=True):
                
                row_dict = dict(zip(headers, row))
                meter_no = row_dict['MFG Serial Number']
                
                try:
                    if len(str(meter_no)) > 0:
                        if Meter.objects.filter(meter_no=meter_no).exists():
                            meter = Meter.objects.get(meter_no=meter_no)
                            meter.linked_phase = phase
                            meter.save()
                            print("FILE: ",fk,'/',files_count,' ROW: ',ct,'/',all_rows_len,meter_no,phase.description,'updated')
                        else:
                            try:
                                Meter.objects.create(
                                    meter_no=meter_no,
                                    linked_phase=phase,
                                    contractor=Contractor.objects.get(company='INTERNAL ISSUE'),
                                    created_by=request.user,
                                    location=Location.objects.get(is_default=True)
                                )
                            except Exception as e:
                                pass
                            print("FILE: ",fk,'/',files_count,' ROW: ',ct,'/',all_rows_len,meter_no,phase.description,'created')
                    else:
                        print("FILE: ",fk,'/',files_count,' ROW: ',ct,'/',all_rows_len,meter_no,phase.description,meter_no,'not found')
                except Meter.DoesNotExist:
                    
                    print("FILE: ",fk,'/',files_count,' ROW: ',ct,'/',all_rows_len,meter_no,phase.description,str(e))

                ct += 1
                total_meters += 1

            fk += 1

            # Documents.objects.create(
            #     doc='SHP',
            #     title=file_name,
            #     entry_no=f'{phase.description} SHIPMENT FILE',
            #     file=excel_file,
            #     description=f'{phase.description} SHIPMENT FILE',
            # )
            
        print({
            'status_code':'202','message':f"{total_meters} meters from {fk} files "}
        )
        return JsonResponse({
            'status_code':'202','message':f"{total_meters} meters from {fk} files "
        })
            
            
        
    else:
        return JsonResponse({'status_code': '400', 'message': 'Invalid method'})


def ecg_reports(request):
    page = {
        "title":"ECG Reports"
    }

    context = {
        'nav':True,
        'page':page
    }


    return render(request,'ssml/ecg/monthly_reports.html',context=context)

@login_required
def ecg_invoice(request):

    
    last_entry = False
    if EcgInvoiceHd.objects.all().count() > 0:
        last_entry = EcgInvoiceHd.objects.all().last().entry_no

    page = {
        'title': 'ECG Invoice',
        'page': 'ecg_invoice',
        'nav': True
    }
    context = {
        'page': page,
        'last_entry': last_entry
    }
    return render(request, 'ssml/ecg/ecg-invoice.html', context=context)

@login_required
def ecg_invoice_new(request):
    page = {
        'title': 'New ECG Invoice',
        'page': 'ecg_invoice',
        'nav': True
    }
    eligible_jobs = ServiceOrder.objects.filter(status='completed', is_ecg_invoiced=False)
    
    context = {
        'page': page,
        'jobs': eligible_jobs
    }
    return render(request, 'ssml/ecg/ecg-invoice-new.html', context=context)

@login_required
def ecg_invoice_edit(request, pk):
    invoice = ECGInvoiceHD.objects.get(pk=pk)
    page = {
        'title': 'Edit ECG Invoice',
        'page': 'ecg_invoice',
        'nav': True
    }
    context = {
        'page': page,
        'invoice': invoice
    }
    return render(request, 'ssml/ecg/ecg-invoice-edit.html', context=context)

@login_required
def ecg_invoice_view(request, pk):
    page = {
        'title': 'View ECG Invoice',
        'page': 'ecg_invoice',
        'nav': True
    }
    context = {
        'page': page,
        'last_entry': pk
    }
    return render(request, 'ssml/ecg/ecg-invoice.html', context=context)

@login_required
def ecg_rates(request):
    page = {
        'title': 'ECG Rates Management',
        'page': 'ecg_invoice',
        'nav': True
    }
    context = {
        'page': page,
        'service_types': ServiceType.objects.all().order_by('name')
    }
    return render(request, 'ssml/ecg/ecg-rates.html', context=context)

@login_required()
def ledger(request):
    page = {
        'title': 'Ledgers',
        'page': 'accounts_ledge',
        'nav': True
    }
    context = {
        'page': page,
        'ledgers':AccountLedger.objects.all().order_by('name')
    }
    return render(request, 'ssml/accounts/ledger.html', context=context)
@login_required()

def journal_voucher(request):
    entry_no = JournalVoucherHd.objects.all().last().entry_no if JournalVoucherHd.objects.all().count() > 0 else ""
    page = {
        'title': 'Journal Voucher',
        'page': 'jv',
        'nav': True
    }
    context = {
        'page': page,
        "entry_no": entry_no
    }
    return render(request, 'ssml/accounts/jv.html', context=context)
@login_required()

def journal_voucher_add(request):
    page = {
        'title': 'New Journal Voucher',
        'page': 'new_jv',
        'nav': True
    }

    options = ""
    for lg in AccountLedger.objects.all():
        options += f"<option value='{lg.pk}'>{lg.name}</option>\n"
    context = {
        'page': page,
        'ledge_options': options
    }
    return render(request, 'ssml/accounts/new_jv.html', context=context)

@csrf_exempt
@login_required()
def update_material(request):
    if request.method == 'POST':
        import openpyxl
        excel_file = request.FILES['excel_file']
        wb = openpyxl.load_workbook(excel_file)
        sheet = wb.active
        headers = [cell.value for cell in sheet[1]]

        r_count = 1
        r_len = sheet.max_row - 1
        for row in sheet.iter_rows(min_row=2, values_only=True):

            row_dict = dict(zip(headers, row))
            meter_no = row_dict['MFG Serial Number']

            materials_message = ''
            print("##" * 5 , meter_no)
            try:
                met_service = ServiceOrder.objects.get(new_meter=meter_no)

                for material in InventoryMaterial.objects.all().order_by('name'):
                    qty = row_dict.get(material.name, 0)
                    # add material or update
                    MaterialOrderItem.objects.filter(service_order=met_service, material=material).delete()

                    if qty > 0:
                        # # print("FISH",material.name,qty)
                        materials_message += f"{material.name} | {qty}\n"

                        MaterialOrderItem(
                            service_order=met_service, material=material, quantity=qty, rate=0, amount=0
                        ).save()

                        print(materials_message)
                        print()

            except Exception as e:
                print(e)

            print('##' * 5, meter_no)


        return JsonResponse({
            'status_code':200,
            'message':"Materials Usage Processed"
        })

    else:
        return JsonResponse({'message': 'There is an error'}, status=400)


@login_required()
def foc_compliance(request):
    page = {
        'title': 'FOC Compliance',
        'page': 'jv',
        'nav': True
    }
    context = {
        'page': page,
    }
    return render(request, 'ssml/foc/complance.html', context=context)


@csrf_exempt
def save_foc_compliance(request):
    if request.method == 'POST':

        try:
            form = request.POST
            foc_code = form.get('foc_code')
            compliance = form.get('compliance')
            cp = FocComplianceType.objects.get(pk=compliance)
            foc = Contractor.objects.get(code=foc_code)
            ref = form.get('ref')



            FocCompliance.objects.create(
                foc=foc,
                c_type=cp,
                ref=ref,
                file=request.FILES['file']
            )

            return JsonResponse({
                'status_code':200,
                "message":"Compliane Updated"
            })

        except Exception as e:
            return JsonResponse({
                'status_code':505,
                "message":str(e)
            })

    else:
        return JsonResponse({'message': 'There is an error',"status_code":505}, status=400)

@login_required()
def foc_comp_list(request,code):
    foc = Contractor.objects.get(code=code)
    comps = FocCompliance.objects.filter(foc=foc)
    page = {
        'title':f"Foc Compliance"
    }

    comp_types = f"<option disabled selected value=''>Select Compliance</option>"
    for ct in FocComplianceType.objects.all():
        comp_types += f"<option value='{ct.pk}'>{ct.name}"

    context = {
        "page": page,
        "nav":True,
        'comps':comps,
        'foc':foc,
        'comp_types':comp_types
    }

    return render(request,'ssml/foc/my-compliance.html',context=context)

@login_required()
@csrf_exempt
def post_foc_invoice(request):
    if request.method == 'POST':
        entry_no = request.POST['entry_no']
        print(request.POST)
        print(entry_no)
        inv = FocInvoiceHd.objects.get(entry_no=entry_no)


        cheque = request.FILES['cheque']
        inv.cheque = cheque
        inv.posted_by = request.user

        EMAIL_INVOICE_RAISED = """
                            <!DOCTYPE html>
                            <html lang="en">
                            <head>
                              <meta charset="UTF-8" />
                              <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
                              <title>Invoice Notification</title>
                              <style>
                                @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap');

                                * {{ margin: 0; padding: 0; box-sizing: border-box; }}

                                body {{
                                  background-color: #f4f4f0;
                                  font-family: 'DM Sans', sans-serif;
                                  color: #1a1a1a;
                                  padding: 40px 16px;
                                }}

                                .wrapper {{ max-width: 560px; margin: 0 auto; }}

                                .card {{
                                  background: #ffffff;
                                  border-radius: 6px;
                                  overflow: hidden;
                                }}

                                .header {{
                                  background: #1a1a1a;
                                  padding: 36px 40px;
                                }}

                                .header .brand {{
                                  font-size: 11px;
                                  font-weight: 500;
                                  letter-spacing: 0.12em;
                                  text-transform: uppercase;
                                  color: rgba(255,255,255,0.45);
                                }}

                                .header .title {{
                                  margin-top: 12px;
                                  font-size: 26px;
                                  font-weight: 300;
                                  color: #ffffff;
                                  line-height: 1.3;
                                }}

                                .header .title span {{ color: #F5C400; }}

                                .accent-bar {{ height: 4px; background: #F5C400; }}

                                .body {{ padding: 36px 40px; }}

                                .greeting {{
                                  font-size: 15px;
                                  font-weight: 500;
                                  margin-bottom: 12px;
                                  color: #1a1a1a;
                                }}

                                .message {{
                                  font-size: 14px;
                                  line-height: 1.8;
                                  color: #555;
                                }}

                                .invoice-box {{
                                  margin: 28px 0;
                                  border: 1px solid #e8e8e8;
                                  border-radius: 4px;
                                  overflow: hidden;
                                }}

                                .invoice-box .inv-header {{
                                  background: #F5C400;
                                  padding: 12px 20px;
                                  font-size: 11px;
                                  letter-spacing: 0.1em;
                                  text-transform: uppercase;
                                  color: #1a1a1a;
                                  font-weight: 500;
                                }}

                                .invoice-row {{
                                  display: flex;
                                  justify-content: space-between;
                                  padding: 13px 20px;
                                  border-top: 1px solid #f0f0f0;
                                  font-size: 13px;
                                }}

                                .invoice-row .label {{ color: #888; }}

                                .invoice-row .value {{
                                  font-family: 'DM Mono', monospace;
                                  font-weight: 500;
                                  color: #1a1a1a;
                                }}

                                .invoice-row.total {{ background: #fafafa; }}

                                .invoice-row.total .value {{ font-size: 15px; }}

                                .cta {{ margin-top: 28px; }}

                                .cta a {{
                                  display: inline-block;
                                  background: #F5C400;
                                  color: #1a1a1a;
                                  text-decoration: none;
                                  font-size: 13px;
                                  font-weight: 500;
                                  letter-spacing: 0.06em;
                                  padding: 13px 26px;
                                  border-radius: 4px;
                                }}

                                .note {{
                                  margin-top: 24px;
                                  font-size: 13px;
                                  color: #aaa;
                                  line-height: 1.7;
                                }}

                                .note a {{ color: #1a1a1a; }}

                                .footer {{
                                  padding: 20px 40px;
                                  border-top: 1px solid #f0f0f0;
                                  font-size: 12px;
                                  color: #bbb;
                                  line-height: 1.7;
                                }}
                              </style>
                            </head>
                            <body>
                              <div class="wrapper">
                                <div class="card">

                                  <div class="header">
                                    <div class="brand">{company_name}</div>
                                    <div class="title">
                                      Invoice <span>#{invoice_number}</span><br/>has been raised.
                                    </div>
                                  </div>

                                  <div class="accent-bar"></div>

                                  <div class="body">
                                    <p class="greeting">Hi {contractor_name},</p>
                                    <p class="message">
                                      An invoice has been generated for your services rendered during the period of
                                      <strong>{period_start}</strong> to <strong>{period_end}</strong>.
                                      Please review the details below.
                                    </p>

                                    <div class="invoice-box">
                                      <div class="inv-header">Invoice Summary</div>
                                      <div class="invoice-row">
                                        <span class="label">Invoice No.</span>
                                        <span class="value">#{invoice_number}</span>
                                      </div>
                                      <div class="invoice-row">
                                        <span class="label">Issue Date</span>
                                        <span class="value">{invoice_date}</span>
                                      </div>
                                      <div class="invoice-row">
                                        <span class="label">Due Date</span>
                                        <span class="value">{due_date}</span>
                                      </div>
                                      <div class="invoice-row total">
                                        <span class="label">Amount Due</span>
                                        <span class="value">{currency} {amount}</span>
                                      </div>
                                    </div>

                                    <div class="cta">
                                      <a href="{invoice_url}">View Invoice &rarr;</a>
                                    </div>

                                    <p class="note">
                                      Questions? Reach out to
                                      <a href="mailto:{support_email}">{support_email}</a>.
                                    </p>
                                  </div>

                                  <div class="footer">
                                    &copy; {year} {company_name} &mdash; This is an automated notification, please do not reply directly to this email.
                                  </div>

                                </div>
                              </div>
                            </body>
                            </html>
                            """
        invoice_date = inv.invoice_date
        from datetime import date
        import calendar

        d = invoice_date

        start = d.replace(day=1)
        end = d.replace(day=calendar.monthrange(d.year, d.month)[1])
        html_body = EMAIL_INVOICE_RAISED.format(
            company_name="Sneda Smart Meters Limited.",
            contractor_name=inv.foc.company,
            invoice_number=inv.entry_no,
            period_start=start,
            period_end=end,
            invoice_date=inv.invoice_date.strftime("%b %d, %Y"),
            due_date="Not Applicable",
            currency='GHS',
            amount=f"{inv.net_amount:.2f}",
            invoice_url=f"Visit your FOC Portal",
            support_email="solomon@snedaghana.com",
            year=timezone.now().year,
        )

        mail_q = MailQueues.objects.create(
            recipient=inv.foc.email,
            subject=f"Payment : {inv.remarks}",
            body=EMAIL_INVOICE_RAISED,
            sender=MailSenders.objects.get(address='solomon@snedaghana.com') if MailSenders.objects.filter(
                address='solomon@snedaghana.com') else MailSenders.objects.get(is_default=True),
            mail_key=make_md5_hash(f"{inv.foc_id}-{EMAIL_INVOICE_RAISED}{EMAIL_INVOICE_RAISED}")
        )

        MailAttachments.objects.create(
            mail=mail_q,
            attachment=cheque
        )

        Sms(
            api=SmsApi.objects.get(is_default=True),
            to=inv.foc.phone,
            message=f"Payment ready for: {inv.remarks}",
        ).save()

        inv.is_posted = True
        inv.save()


        return JsonResponse({'status': 'success'})

    else:
        return JsonResponse({'message': 'There is an error'}, status=400)

@login_required()
def agents(request):
    context = {
        'page': {
            'nav':True,
            'title':'Agents'
        },
        'agents':Agents.objects.all()

    }
    return render(request, 'ssml/foc/agents.html', context=context)

@login_required()
def retire_request(request,agen_code):
    if Agents.objects.filter(code=agen_code).exists():
        agent = Agents.objects.get(code=agen_code)
        context = {
            'page': {
                'nav': True,
                'title': 'Retirement Request'
            },
            'pending': Retiring.objects.filter(agent=agent,is_verified=False)

        }
        return render(request, 'ssml/meters/retirement-request.html', context=context)
    else:
        return HttpResponse("Agent Does Not Exist")

@csrf_exempt
def approve_retirement(request):
    if request.method == 'POST':
        print(request.POST)
        print(request.FILES)
        try:
            pk = request.POST.get('pk')
            foc_code = request.POST.get('agent_code')
            image = request.FILES.get('image')

            # todo:: validate meters belongs to foc


            agent  = Agents.objects.get(code=foc_code)
            meter = Retiring.objects.get(pk=pk,agent=agent)
            if ServiceOrder.objects.filter(new_meter=meter.new_meter).exists():
                service = ServiceOrder.objects.get(new_meter=meter.new_meter)
                service_foc = service.contractor
                agent_foc = agent.foc

                if service_foc != agent_foc:
                    # raise issue
                    ContractorError.objects.create(
                        contractor=agent_foc,
                        error_date=timezone.now(),
                        error_type='DAM',
                        description=f"{agent.first_name} {agent.last_name} tried to retire a meter installed by {service_foc.company}",
                        meter=Meter.objects.get(meter_no=meter.new_meter),

                    )
                    meter.delete()
                    raise Exception(f"Meter was installed by {service_foc.company} not {agent_foc.company}. Record deleted")

            else:
                raise Exception("New Meters does not exist / synced")


            meter.is_verified = True
            meter.image = image
            meter.save()

            return JsonResponse({'status_code':200, 'message':"Approved" })
        except Exception as e:
            return JsonResponse({'status_code': 505, 'message': str(e)})

    else:
        return JsonResponse({'status_code':505, 'message':"Invalid Form" })

@login_required()
def import_agents(request):
    import pandas as pd

    excel_file = request.FILES['agent_file']

    df = pd.read_excel(excel_file)  # first row = headers by default

    # Loop through rows


    for index, row in df.iterrows():


        foc_code = row['CONTRACTOR CODE']
        first_name = row['OTHER NAMES']
        last_name = row['LASTNAME']
        email = row['EMAIL ADDRESS']
        phone = str(row['PHONE NUMBER'])
        phone = f"0{phone.replace('+','')[3:]}"
        ghana_card = row['GHANA CARD NUMBER']
        agent_code = row['AGENT CODE']
        li = [foc_code, agent_code, first_name, last_name, phone, email, ghana_card]
        foc = Contractor.objects.get(code=foc_code)

        print(li)
        # confirm with agent created
        if Agents.objects.filter(code=agent_code).exists():
            print(f"{first_name} {last_name} Exists")
        else:
            try:
                Agents.objects.create(
                            first_name=first_name,
                            last_name=last_name,
                            phone=phone,
                            email=email,
                            foc=foc,
                            ghana_card=ghana_card,
                            code=agent_code,
                            is_approved=True
                        )

                foc_sms = (
                            f"Dear {first_name} {last_name}, your data has been submitted by {foc.company} to add as agent, review your information below\n"
                            f"Name: {first_name} {last_name}\nEmail:{email}\nGhana Card: {ghana_card}")

                Sms.objects.create(
                            api=SmsApi.objects.get(is_default=True),
                            to=phone,
                            message=foc_sms
                        )
            except Exception as e:
                print(e)
            print(f"{first_name} {last_name} Does Not Exists")


        print()




    # return HttpResponse("YAMUTY")
    return redirect(request.META.get('HTTP_REFERER'))
