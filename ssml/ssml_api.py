import os
from calendar import monthrange

import now
from django.db.models import Model

from accounts.models import Ledger, JVHeader, SubLedger, JVTransaction
from admin_panel.anton import shorten_url
from admin_panel.models import UserAddOns
from crm.views import contacts
from ocean.settings import COMPANY_DETAILS
from ssml.helper import generate_entry_entry
from ssml.models import ServiceOrderType, InstallationTypePhaseRate, AccountLedger, \
    JournalVoucherHd, JournalVoucherTransactions, FocInvoiceHd, FocInvoiceTransactions, FocInvoiceAssets, \
    FocComplianceType, EcgInvoiceAssets, EcgInvoiceTransactions, EcgInvoiceHd, FocCompliance


def safe_add_image_to_pdf(pdf, image_path, x, y, w, h=None):
    """
    Safely add an image to PDF with fallback options
    """
    import os
    
    # Try the original image path first
    if os.path.exists(image_path):
        try:
            if h:
                pdf.image(image_path, x=x, y=y, w=w, h=h)
            else:
                pdf.image(image_path, x=x, y=y, w=w)
            return True
        except Exception as e:
            print(f"Warning: Could not load image {image_path}: {e}")
    
    # If original fails, try fallback options
    fallback_paths = [
        'static/general/img/logo.png',
        'static/general/img/logo-blue.png',
        'static/general/img/sneda_motors_logo.png'
    ]
    
    for fallback_path in fallback_paths:
        if os.path.exists(fallback_path) and fallback_path != image_path:
            try:
                if h:
                    pdf.image(fallback_path, x=x, y=y, w=w, h=h)
                else:
                    pdf.image(fallback_path, x=x, y=y, w=w)
                print(f"Used fallback image: {fallback_path}")
                return True
            except Exception as e:
                print(f"Warning: Could not load fallback image {fallback_path}: {e}")
                continue
    
    # If all images fail, just skip the logo
    print("Warning: No logo images could be loaded, skipping logo")
    return False

from django.views.decorators.csrf import csrf_exempt
@csrf_exempt
def interface(request):
    import json
    import sys
    from decimal import Decimal
    from django.http import JsonResponse

    from django.db.models import Q
    from django.contrib.auth.models import User,Group
    from ocean.settings import BASE_URL

    from ssml.models import Cardex, Location, RequiredReturn, InvoiceHD, InvoiceTransactions, Contractor, Expense, \
        InventoryGroup, InventoryMaterial, Issue, IssueTransaction, MaterialOrderItem, Meter, PaySlipHD, Plot, \
        RedeemTransactions, Reedem, Service, ServiceMaterials, ServiceOrder, ServiceOrderItem, ServiceOrderReturns, \
        ServiceType, Supplier, Grn, GrnTransaction, ContractorError, TransferHd, TransferTr,InstallationType,PettyCash,RetiredMetersBox,RetiredMetersTransactions,Phase, \
        ECGJobRate, ECGMeterRate
    from admin_panel.models import Emails, Locations, BusinessEntityTypes, MailSenders, MailQueues, MailAttachments, \
        Sms, SmsApi
    from admin_panel.anton import make_md5_hash
    response = {
        'status_code': 0,
        'message': ""
    }

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
            if module == 'contractor':
                link = data.get('link')
                company = data.get('company')
                owner = data.get('owner')
                phone = data.get('phone')
                email = data.get('email')
                country = data.get('country')
                city = data.get('city')
                postal_code = data.get('postal_code')
                gh_post_code = data.get('gh_post_code')
                gh_card_no = data.get('gh_card_no')
                created_by = User.objects.get(id=data.get('mypk'))
                code = data.get('code')

                
                Contractor.objects.create(code=code,link=link,company=company, owner=owner, phone=phone,email=email,country=country,
                                          city=city,postal_code=postal_code,gh_card_no=gh_card_no,gh_post_code=gh_post_code,created_by=created_by)

                success_response['message'] = "Contractor Created Successfully"

            elif module == 'link_phase_to_material':
                phase = Phase.objects.get(pk=data.get('phase'))
                material = InventoryMaterial.objects.get(barcode=data.get('barcode'))

                phase.material = material
                phase.save()
                phase = Phase.objects.get(pk=data.get('phase'))


            elif module == 'foc_compliance_type':
                mypk = data.get('mypk')
                name = data.get('name')
                description = data.get('description')
                is_required = data.get('is_required')
                if is_required == 'YES':
                    is_required = True
                else:
                    is_required = False

                FocComplianceType.objects.create(
                    name=name,
                    description=description,
                    is_required=is_required
                )

                success_response['message'] = "Foc Compliance Type Created Successfully"

            elif module == 'save_invoice':

                print(data)
                header = data.get('header')
                user = User.objects.get(pk=header.get('mypk'))
                transactions = data.get('transactions')
                foc = Contractor.objects.get(code=header.get('new_foc_name'))
                if not foc.is_complied().get('status'):
                    pass
                    # raise Exception("FOC is not complied")

                invoice_date = header.get('new_invoice_date')
                loc_id = header.get('new_loc_id')
                location = Location.objects.get(loc_id=loc_id)
                # log meters of invoices that pass
                from datetime import date, datetime

                d = datetime.strptime(invoice_date, '%Y-%m-%d').date()


                first_day = date(d.year, d.month, 1)
                last_day = date(d.year, d.month, monthrange(d.year, d.month)[1])
                services = ServiceOrder.objects.filter(
                    contractor=foc,
                    service_date__gte=first_day,service_date__lte=last_day,
                    flag_for_invoice=True,
                    location=location
                )

                if services.count() < 0:
                    raise Exception("Cannot save invoice becuase no related services for location and month")


                if len(transactions) > 0:
                    entry_no = f"FOC-INV-{FocInvoiceHd.objects.all().last().pk + 1 if FocInvoiceHd.objects.all().count() > 0 else 1}"
                    FocInvoiceHd.objects.create(
                        entry_no=entry_no,
                        foc=foc,
                        remarks=header.get('new_remarks'),
                        invoice_date=header.get('new_invoice_date'),
                        created_by=user,
                        location=location
                    )

                    invoice = FocInvoiceHd.objects.get(entry_no=entry_no)
                    for tran in transactions:
                        quantity = Decimal( tran.get('quantity'))
                        rate = Decimal(tran.get('rate'))
                        amount = quantity * rate

                        FocInvoiceTransactions.objects.create(
                            invoice=invoice,
                            item=tran.get('item'),
                            rate=rate,
                            amount=amount,
                            quantity=quantity

                        )

                    invoice.update_totals()

                    # add invoice assets
                    for service in services:

                        installation_type = service.installation_type
                        sts = service.new_meter
                        print(sts)
                        spn=service.spn
                        phase = service.meter_phase()

                        if not FocInvoiceAssets.objects.filter(sts=sts).exists():
                            FocInvoiceAssets.objects.create(
                                invoice=invoice,
                                sts=sts,
                                spn=spn,
                                installation=installation_type.name,
                                phase=phase
                            )

                    invoice.update_totals()









                    success_response['message'] = f"Invoice created with entry {entry_no}"

                else:
                    raise Exception("Cannot Save Empty Invoice")

            elif module == 'save_ecg_invoice':

                print(data)
                header = data.get('header')
                user = User.objects.get(pk=header.get('mypk'))
                transactions = data.get('transactions')


                invoice_date = header.get('new_invoice_date')
                loc_id = header.get('new_loc_id')
                location = Location.objects.get(loc_id=loc_id)
                # log meters of invoices that pass
                from datetime import date, datetime

                d = datetime.strptime(invoice_date, '%Y-%m-%d').date()


                first_day = date(d.year, d.month, 1)
                last_day = date(d.year, d.month, monthrange(d.year, d.month)[1])
                services = ServiceOrder.objects.filter(

                    service_date__gte=first_day,service_date__lte=last_day,
                    flag_for_invoice=True,
                    location=location
                )

                if services.count() < 0:
                    raise Exception("Cannot save invoice becuase no related services for location and month")


                if len(transactions) > 0:
                    entry_no = f"ECG-INV-{EcgInvoiceHd.objects.all().last().pk + 1 if EcgInvoiceHd.objects.all().count() > 0 else 1}"
                    EcgInvoiceHd.objects.create(
                        entry_no=entry_no,
                        remarks=header.get('new_remarks'),
                        invoice_date=header.get('new_invoice_date'),
                        created_by=user,
                        location=location
                    )

                    invoice = EcgInvoiceHd.objects.get(entry_no=entry_no)
                    for tran in transactions:
                        quantity = Decimal( tran.get('quantity'))
                        rate = Decimal(tran.get('rate'))
                        amount = quantity * rate

                        EcgInvoiceTransactions.objects.create(
                            invoice=invoice,
                            service=tran.get('service'),
                            rate=rate,
                            amount=amount,
                            quantity=quantity,
                            service_type=tran.get('s_type')

                        )

                    invoice.update_totals()

                    # add invoice assets
                    for service in services:

                        installation_type = service.installation_type
                        sts = service.new_meter
                        print(sts)
                        spn=service.spn
                        phase = service.meter_phase()

                        if not EcgInvoiceAssets.objects.filter(sts=sts).exists():
                            EcgInvoiceAssets.objects.create(
                                invoice=invoice,
                                sts=sts,
                                spn=spn,
                                installation=installation_type.name,
                                phase=phase
                            )

                    invoice.update_totals()









                    success_response['message'] = f"Invoice created with entry {entry_no}"

                else:
                    raise Exception("Cannot Save Empty Invoice")


            elif module == 'jv_entry':
                entry_date = data.get('entry_date')
                narration = data.get('narration')
                created_by = User.objects.get(pk=data.get('mypk'))
                transactions = data.get('transactions')

                # make entry no
                entry_no = f"JV{JournalVoucherHd.objects.all().last().pk + 1 if JournalVoucherHd.objects.all().last() else 1}"
                JournalVoucherHd.objects.create(
                    entry_no=entry_no,
                    entry_date=entry_date,
                    narration=narration,
                    created_by=created_by
                )

                hd = JournalVoucherHd.objects.get(entry_no=entry_no)
                total_debit = 0
                total_credit = 0

                for transaction in transactions:
                    ledger = AccountLedger.objects.get(pk=transaction.get('ledger'))
                    debit = transaction.get('debit')
                    credit = transaction.get('credit')

                    total_debit += debit
                    total_credit += credit

                    JournalVoucherTransactions.objects.create(
                        hd=hd,
                        ledger=ledger,
                        debit=debit,
                        credit=credit,
                        description=transaction.get('description'),
                        created_by=created_by
                    )

                # update header
                hd.total_debit = total_debit
                hd.total_credit = total_credit
                hd.save()

                success_response['message'] = "Journal Voucher Created Successfully"

            elif module == 'ledger':
                created_by = User.objects.get(pk=data.get('mypk'))
                ledger_name = data.get('ledger_name')
                ledger_desc = data.get('ledger_desc')
                ref = data.get('foc')
                ob = data.get('opening_balance')
                key = make_md5_hash(f'{ledger_name}{ledger_desc}')

                AccountLedger.objects.create(name=ledger_name, description=ledger_desc, reference=ref, created_by=created_by,key=key)

                ledger = AccountLedger.objects.get(key=key)



                

                success_response['message'] = "Ledger Created Successfully"





            elif module == 'phase':
                # INSERT_YOUR_CODE
                phase_number = data.get('phase_number')
                phase_description = data.get('phase_description')
                owner = User.objects.get(pk=data.get('mypk'))

                # Implement your logic here for adding a phase (e.g., saving to DB)
                # Assuming you have a Phase model:
                # from ssml.models import Phase

                Phase.objects.create(number=phase_number, description=phase_description, created_by=request.user)

                success_response['message'] = "Phase Created Successfully"

            elif module == 'sync_retired_meters':
                

                try:

                    #RetiredMetersBox.objects.all().delete()
                    box_no = data.get('box_no')
                    location = Location.objects.get(loc_id=data.get('loc_id'))

                    sheet_name = f"Box {box_no}"
                    
                    

                    import gspread
                    from oauth2client.service_account import ServiceAccountCredentials

                    # Path to your service account key
                    # SERVICE_ACCOUNT_FILE = 'static\general\oth\ssml.json' 
                    print("Getting FIle")
                    print("FILE FROM DB",location.auth_file_path())
                    print("Getting FIle")
                    SERVICE_ACCOUNT_FILE = str(location.auth_file_path())
                    print("PASSED FILE",SERVICE_ACCOUNT_FILE)

                    # 1. Set up Google Sheets API client
                    scope = [
                        'https://spreadsheets.google.com/feeds',
                        'https://www.googleapis.com/auth/drive'
                    ]
                    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
                    gc = gspread.authorize(creds)

                    # 2. Open the Google Sheet
                    sheet_url = 'https://docs.google.com/spreadsheets/d/1RrN2zKophgm3Dz9PzewqbNfdU8B8hbnFPdBwVoZv4YI/edit?usp=sharing'
                    sheet_url = location.boxing_file_link
                    # print("LINK:",sheet_url)
                    sh = gc.open_by_url(sheet_url)

                    # print("CONNECTED TO GOOGLE SHEET")

                    print("\nBOX NUMBER:",box_no)
                    ServiceOrder.objects.all().update(
                                            is_boxed = False,
                                            box_no = 0,
                                            final_readings=0
                                            
                                        )
                    RetiredMetersBox.objects.filter(box_no=box_no,location=location).delete()
                    # RetiredMetersBox.objects.all().delete()

                    if not RetiredMetersBox.objects.filter(box_no=box_no,location=location).exists():
                                RetiredMetersBox.objects.create(
                                    box_no=box_no,
                                    created_by=User.objects.get(pk=data.get('mypk')),
                                    location=location
                                )
                    box = RetiredMetersBox.objects.get(box_no=box_no,location=location)

                    # Make sheetname lookup case insensitive
                    worksheet = None
                    all_worksheets = sh.worksheets()
                    for ws in all_worksheets:
                        if ws.title.lower() == sheet_name.lower():
                            worksheet = ws
                            break
                    if worksheet is None:
                        print(f"Cannot Find WOrksheet {sheet_name}")
                        raise Exception(f"Worksheet '{sheet_name}' (case-insensitive) not found in the Google Sheet.")
                
                    # Loop from row 7 to 31 (inclusive) and print each row's values
                    all_rows = worksheet.get_all_values()[6:]
                    print(sheet_name, "has",len(all_rows),'rows')
                    for row in all_rows:
                        try:
                            empt,sn,box_no,spn,old_meter_no,diff_old_meter_no,ppm_cm,final_readings,rem_wattage,rem_cedis,make_year,manufacturere,has_uiu,phase,has_enclosure,has_sim_card,ret_cable_length,rating,date_removed,reason,has_breaker,foc = row[:22]
                            
                                                
                            
                            li = [sn,box_no,spn,old_meter_no,diff_old_meter_no,ppm_cm,final_readings,rem_wattage,rem_cedis,make_year,manufacturere,has_uiu,phase,has_enclosure,has_sim_card,ret_cable_length,rating,date_removed,reason,has_breaker,foc]
                            # print(sn,spn)
                            # print(box.box_no)
                            if RetiredMetersTransactions.objects.filter(old_meter_no=old_meter_no).exists():
                                print("box",box_no,"LINE",sn,"Old Meter Is Duplicate")
                                old_meter_no += "D"
                                

                            try:
                                final_readings = float(final_readings)
                            except (ValueError, TypeError):
                                final_readings = 0

                            if RetiredMetersTransactions.objects.filter(spn=spn).count() == 0:
                            
                                # Example: get contractor with company like foc
                                # if not Contractor.objects.filter(company__icontains=foc).exists():
                                #     foc = "INTERNAL"
                                
                                contractor = Contractor.objects.filter(company__icontains=foc).last()
                                
                            
                                # print("Before Date")
                                if len(box_no) > 0:
                                    try:
                                        

                                        # print('date removed:',date_removed)
                                        # # get proper removed date
                                        if ServiceOrder.objects.filter(spn=spn).exists():
                                            ct = ServiceOrder.objects.filter(spn=spn).count()
                                            date_removed = ServiceOrder.objects.filter(spn=spn).last().service_date
                                            ServiceOrder.objects.filter(spn=spn).update(
                                                is_boxed = True,
                                                box_no = data.get('box_no'),
                                                final_readings=final_readings
                                                
                                            )

                                            # print("FINAL READING SET:",final_readings)
                                            
                                            # print(f"THERE IS SPN {spn} {date_removed}")

                                        else:
                                            # if date_removed:
                                            from datetime import datetime
                                            try:
                                                # Try DD/MM/YYYY HH:MM
                                                date_removed = datetime.strptime(date_removed, '%d/%m/%Y %H:%M').date()
                                            except ValueError:
                                                try:
                                                    # Try MM/DD/YYYY
                                                    date_removed = datetime.strptime(date_removed, '%m/%d/%Y').date()
                                                except ValueError:
                                                    try:
                                                        # Try DD/MM/YYYY HH:MM
                                                        # Try MM/DD/YYYY HH:MM
                                                        date_removed = datetime.strptime(date_removed, '%m/%d/%Y %H:%M').date()
                                                    except ValueError:
                                                        try:
                                                            # Try DD/MM/YYYY
                                                            date_removed = datetime.strptime(date_removed, '%d/%m/%Y').date()
                                                        except Exception as e:
                                                            print(f"Failed to parse date_removed '{date_removed}': {e}")
                                                            date_removed = None
                                            print("NO SPN")

                                        if len(diff_old_meter_no) > 0:
                                            # print("There is different meter_no")
                                            ServiceOrder.objects.filter(spn=spn).update(
                                                is_boxed = True,
                                                box_no = data.get('box_no')
                                            )
                                        else:
                                            pass   

                                        RetiredMetersTransactions(
                                            box=box,
                                            sn=sn,
                                            spn=spn,
                                            old_meter_no=old_meter_no,
                                            diff_old_meter_no=diff_old_meter_no,
                                            ppm_cm=ppm_cm,
                                            final_readings=final_readings,
                                            rem_wattage=rem_wattage,
                                            rem_cedis=rem_cedis,
                                            make_year=make_year,
                                            manufacturere=manufacturere,
                                            has_uiu=has_uiu,
                                            phase=phase,
                                            has_enclosure=has_enclosure,
                                            has_sim_card=has_sim_card,
                                            ret_cable_length=ret_cable_length,
                                            rating=rating,
                                            date_removed=date_removed,
                                            reason=reason,
                                            has_breaker=has_breaker,
                                            foc=contractor
                                        ).save()

                                        

                                        this_record = RetiredMetersTransactions.objects.filter(spn=spn).last()
                                    

                                        #print("DONE: ",sn,spn,this_record.id)       
                                    
                                    
                                    except Exception as e:
                                        import sys
                                        import traceback
                                        exc_type, exc_value, exc_tb = sys.exc_info()
                                        tb = traceback.extract_tb(exc_tb)
                                        if tb:
                                            line_number = tb[-1].lineno
                                            print(f"[Exception on line {line_number}] {sn} {str(e)}")
                                        else:
                                            print(f"[Exception] {sn} {str(e)}")

                                
                            else:
                                pass
                                print(spn,"SYNCED")
                        except Exception as l:
                            print(":LEGEND:",str(l))
                except Exception as e:
                    #print(str(e))
                    raise Exception(e)
                all_data = {}
                
                    
                response['sheets_processed'] = {
                    k: len(v) for k, v in all_data.items()
                }
                success_response['message'] = "Retired meter sheets read successfully"


            elif module == 'petty_cash':
                dt = data.get('date')
                location = Location.objects.get(pk=data.get('sidebar-location-select'))
                user = User.objects.get(pk=data.get('mypk'))
                from datetime import datetime
                month = datetime.strptime(dt, '%Y-%m-%d').month
                year = datetime.strptime(dt, '%Y-%m-%d').year

                if Expense.objects.filter(date__month=month).exists():
                    entry_no = f"SSML-PTC-{month}-{year}"

                    try:
                        if PettyCash.objects.filter(entry_no=entry_no).exists():
                            raise Exception("Already exists")
                        total_in = 0
                        total_out = 0
                        total = 0
                        for tran in Expense.objects.filter(date__month=month):
                            tran.entry_no = entry_no
                            total += tran.amount
                            if tran.direction == 'in':
                                total_in += total
                            if tran.direction == 'out':
                                total_out += total

                            tran.save()
                        # save headr
                        PettyCash.objects.create(
                            date=dt,
                            month=month,
                            total_out = total_out,
                            total_in = total_in,
                            total=total,
                            remarks=f"Petty Cash transaction for the month {month}",
                            created_by=user,
                            entry_no=entry_no,
                            location=location
                        )
                    except Exception as e:
                        Expense.objects.filter(entry_no=entry_no).update(entry_no='')
                        raise Exception(str(e))

                else:
                    raise Exception("No data month")

                success_response['message'] = f"Petty Cash Created Successfully for month {month}"


            elif module == 'order_type':
                st_name = data.get('st_name')
                st_desc = data.get('st_desc')
                st_rate = data.get('st_rate')
                created_by = User.objects.get(id=data.get('mypk'))
                ServiceOrderType.objects.create(name=st_name,description=st_desc,rate=st_rate,created_by=created_by)
                success_response['message'] = "Order Type Created Successfully"

            elif module == 'new_installation_type':
                name = data.get('name')
                description = data.get('description')
                created_by = User.objects.get(id=data.get('mypk'))
                InstallationType.objects.create(name=name, description=description, created_by=created_by)
                success_response['message'] = "Installation Type Created Successfully"

            elif module == 'daily_sms_report':
                from django.utils import timezone
                from datetime import datetime
                print(data)
                day_date = data.get('date',datetime.now().date())
                print(day_date)

                import openpyxl
                
                for contractor in Contractor.objects.all():
                    today_jobs = ServiceOrder.objects.filter(contractor=contractor,service_date=day_date)
                    total_jobs = ServiceOrder.objects.filter(contractor=contractor).count()

                    if today_jobs.count() > 0:
                        book = openpyxl.Workbook()
                        sheet = book.active
                        sheet.title = str(day_date)
                        sheet.append(['METER NUMBER','SERVICE TYPE'])
                        for job in today_jobs:
                            sheet.append([job.new_meter,job.service_type.name])
                        
                        
                        file_name = f"static/general/tmp/daily_report_{contractor.company.replace(' ','_')}_{str(day_date).replace('-','_')}.xlsx"
                        file_url = f"{BASE_URL}{file_name}"

                        import requests

                        long_url = file_url
                        api_url = "https://is.gd/create.php"

                        params = {
                            "format": "simple",  # "simple" returns just the short URL as text
                            "url": long_url
                        }

                        response = requests.get(api_url, params=params)
                        print(response)

                        if response.status_code == 200:
                            file_url = response.text
                        else:
                            print("Error:", response.text)


                        book.save(file_name)
                        sms_message = f"Daily SMS Report for {contractor.company} on {day_date}\nToday Jobs: {today_jobs.count()}\nTotal Jobs: {total_jobs}\n\nDownload the report: \n{file_url}"
                        print(sms_message)
                        to = contractor.phone.replace('233','0').replace('+233','0')
                        if len(to) == 10:
                            Sms(
                                api=SmsApi.objects.get(is_default=True),
                                to=to,
                                message=sms_message
                            ).save()
                    
                    
                    

            elif module == 'return_qty':
                service_id = data.get('service_id')
                transactions = data.get('transactions')
                st = ServiceType.objects.get(id=service_id)
                qty_as_of = data.get('qty_as_of')

                for tran in transactions:
                    idd = tran.get('id')
                    qty = tran.get('qty')

                    print(tran)

                    RequiredReturn.objects.create(
                        service_type=st,
                        material_id=idd,
                        as_of=qty_as_of,
                        quantity=qty
                    )

                success_response['message'] = "Operated"
                response = success_response

            elif module == 'service_materials':
                barcode = data.get('barcode')
                material = InventoryMaterial.objects.get(barcode=barcode)
                ser_id = data.get('service')
                qty = data.get('qty')
                phase = data.get('phase')

                errors = 0
                for p in phase:
                    try:
                        ServiceMaterials.objects.create(
                            service_id=ser_id,
                            material=material,
                            qty=qty,
                            phase=Phase.objects.get(number=p)
                    )
                    except Exception as e:
                        print(e)
                        errors += 1

                success_response['message'] = "Created with " + str(errors) + " errors"
                response = success_response

            elif module == 'location':
                loc_id = data.get('loc_id')
                loc_name = data.get('loc_name')
                loc_desc = data.get('loc_desc')
                country = data.get('country')
                city = data.get('city')
                street = data.get('street')
                address = data.get('address')
                phone = data.get('phone')
                email = data.get('email')
                created_by = User.objects.get(pk=data.get('mypk'))


                Location.objects.create(
                    loc_id=loc_id,
                    loc_name=loc_name,
                    loc_desc = loc_desc,
                    country=country,
                    street=street,
                    address=address,
                    phone=phone,
                    email=email,
                    city=city
                )



            elif module == 'finance':
                direction = data.get('direction')
                date = data.get('date')
                category = data.get('category')
                transaction_type = data.get('transaction_type')
                amount = Decimal(data.get('amount'))
                reference = data.get('reference')
                description = data.get('description')
                created_by = User.objects.get(id=data.get('mypk'))

                print(data)

                if direction == 'out':
                    amount = amount * -1
                Expense.objects.create(direction=direction, date=date, category=category, transaction_type=transaction_type, amount=amount, reference=reference, description=description, created_by=created_by)
                success_response['message'] = "Expense Created Successfully"

            elif module == 'invoice':

                if  InvoiceHD.objects.filter(is_approved=False).exists():
                    raise Exception("You have unposted entries")
               
                try:
                    entry_no = f"SSML-INV-1" if InvoiceHD.objects.all().count() == 0 else f"SSML-INV-{InvoiceHD.objects.all().last().id + 1}"
                    contractor_id = data.get('contractor')
                    contractor = Contractor.objects.get(id=contractor_id)
                    entry_date = data.get('entry_date')
                    remarks = data.get('remarks')
                    transactions = data.get('transactions')
                    created_by = User.objects.get(pk=data.get('mypk'))

                    # save hd
                    InvoiceHD(
                        entry_no=entry_no,
                        entry_date=entry_date,
                        contractor=contractor,
                        remarks=remarks,
                        created_by=created_by
                    ).save()

                    entry = InvoiceHD.objects.get(entry_no=entry_no)

                    print(transactions)

                    total = 0
                    # loop transactions
                    for transaction in transactions:
                        InvoiceTransactions(
                            entry=entry,
                            service_date=transaction.get('date'),
                            asset=transaction.get('meter'),
                            amount=transaction.get('amount'),
                            remarks=transaction.get('service')
                        ).save()
                        print(transaction)

                        # update service order to invoice number


                        total += Decimal(transaction.get('amount'))

                    success_response['message'] = "Invoice Created"
                    entry.total_amount = total
                    entry.save()
                except Exception as e:
                    # Roll back any Issue transactions created
                    if 'entry' in locals():
                        InvoiceHD.objects.filter(entry=entry).delete()
                        entry.delete()  
                    success_response['status_code'] = 400
                    success_response['message'] = f"Error on line {sys.exc_info()[2].tb_lineno}: {e}"

            elif module == 'ecg_invoice':
                try:
                    location_id = data.get('location')
                    location = Location.objects.get(id=location_id)
                    
                    # Sequential invoice number: ECG-INV-{LOCATION_ID}-{YEAR}-{SEQ}
                    year = datetime.now().year
                    seq = EcgInvoiceHd.objects.filter(location=location, entry_date__year=year).count() + 1
                    entry_no = f"ECG-INV-{location.loc_id}-{year}-{seq:04d}"
                    
                    entry_date = data.get('entry_date')
                    remarks = data.get('remarks')
                    job_transactions = data.get('job_transactions', [])
                    meter_transactions = data.get('meter_transactions', [])
                    material_transactions = data.get('material_transactions', [])
                    created_by = User.objects.get(pk=data.get('mypk'))

                    ecg_hd = EcgInvoiceHd(
                        entry_no=entry_no,
                        entry_date=entry_date,
                        location=location,
                        remarks=remarks,
                        created_by=created_by
                    )
                    ecg_hd.save()

                    total = 0
                    # Process Job Transactions
                    for job in job_transactions:
                        so = ServiceOrder.objects.get(id=job.get('id'))
                        ECGInvoiceTransactions(
                            entry=ecg_hd,
                            service_order=so,
                            amount=job.get('amount')
                        ).save()
                        
                        so.is_ecg_invoiced = True
                        so.status = 'ecg_invoiced'
                        so.save()
                        total += Decimal(str(job.get('amount')))
                    
                    # Process Meter Transactions
                    for m_item in meter_transactions:
                        meter_no = m_item.get('meter_no')
                        phase = m_item.get('phase')
                        
                        # Find rate
                        rate_obj = ECGMeterRate.objects.filter(phase__icontains=phase).first()
                        amt = rate_obj.rate if rate_obj else Decimal('0.00')
                        
                        is_found = False
                        if Meter.objects.filter(meter_no=meter_no).exists():
                            m = Meter.objects.get(meter_no=meter_no)
                            m.ecg_invoice_no = entry_no
                            m.save()
                            is_found = True
                        
                        ECGInvoiceItem(
                            entry=ecg_hd,
                            meter_no=meter_no,
                            phase=phase,
                            amount=amt,
                            is_found=is_found
                        ).save()
                        total += amt

                    # Process Material Transactions
                    for mat in material_transactions:
                        material = InventoryMaterial.objects.get(id=mat.get('id'))
                        ECGInvoiceMaterial(
                            entry=ecg_hd,
                            material=material,
                            quantity=mat.get('qty'),
                            rate=mat.get('rate'),
                            amount=mat.get('amount')
                        ).save()
                        total += Decimal(str(mat.get('amount')))
                    
                    ecg_hd.total_amount = total
                    ecg_hd.save()
                    success_response['message'] = f"ECG Invoice {entry_no} Created Successfully"
                except Exception as e:
                    if 'ecg_hd' in locals():
                        ECGInvoiceTransactions.objects.filter(entry=ecg_hd).delete()
                        ECGInvoiceItem.objects.filter(entry=ecg_hd).delete()
                        ECGInvoiceMaterial.objects.filter(entry=ecg_hd).delete()
                        ecg_hd.delete()
                    raise Exception(e)

            elif module == 'ecg_job_rate':
                try:
                    service_type_id = data.get('service_type')
                    service_type = ServiceType.objects.get(id=service_type_id)
                    rate = data.get('rate')
                    created_by = User.objects.get(id=data.get('mypk'))
                    
                    ECGJobRate.objects.update_or_create(
                        service_type=service_type,
                        defaults={'rate': rate, 'created_by': created_by}
                    )
                    success_response['message'] = "Job Rate Updated"
                except Exception as e:
                    raise Exception(e)

            elif module == 'ecg_meter_rate':
                try:
                    phase = data.get('phase')
                    rate = data.get('rate')
                    ECGMeterRate.objects.update_or_create(
                        phase=phase,
                        defaults={'rate': rate}
                    )
                    success_response['message'] = "Meter Rate Updated"
                except Exception as e:
                    raise Exception(e)

            elif module == 'approve_invoice':
                id = data.get('id')
                foc_debt = data.get('foc_debt')
                foc_debt_reason = data.get('foc_debt_reason')
                for invoice in InvoiceHD.objects.filter(id=id):
                    # mark meters
                    for transaction in invoice.transactions():
                        print(transaction)
                        service = ServiceOrder.objects.get(new_meter=transaction.get('asset'))

                        status = service.status
                        service.status = 'invoiced'
                        service.inv_number = invoice.entry_no
                        service.inv_date = invoice.entry_date

                        service.save()
                        print(status)

                    invoice.is_approved = True
                    invoice.doc_debt = foc_debt
                    invoice.foc_debt_reason = foc_debt_reason
                    invoice.approved_by = User.objects.get(pk=data.get('mypk'))
                    invoice.save()



            elif module == 'post_invoice':
                from django.utils import timezone
                id = data.get('id')
                try:
                    approved_by = User.objects.get(pk=data.get('mypk'))
                    invoice = InvoiceHD.objects.get(id=id)
                    transactions = invoice.transactions()
                    for transaction in transactions:
                        # mark meters
                        service = ServiceOrder.objects.get(new_meter=transaction.get('asset'))
                        status = service.status
                        service.status = 'invoiced'
                        service.inv_number = invoice.entry_no
                        service.inv_date = invoice.entry_date
                        service.save()
                        print(status)

                    ## make FOC







                except Exception as e:
                    InvoiceHD.objects.filter(id=id).update(is_posted=False)
                    print(f"Error posting invoice: {e}")

            elif module == 'meters':
                meters = data.get('meters')
                meter_type = data.get('meter_type')
                created_by = User.objects.get(id=data.get('mypk'))
                contractor = Contractor.objects.get(id=data.get('contractor'))

                for meter in meters:
                    try:
                        Meter.objects.create(meter_no=meter, meter_type=meter_type, created_by=created_by, contractor=contractor)
                    except Exception as e:
                        print(e)
                        pass
                success_response['message'] = "Meters Created Successfully" 

            elif module == 'group':
                name = data.get('name')
                InventoryGroup.objects.create(name=name)
                success_response['message'] = "Group Created Successfully"
            elif module == 'material':
                barcode = data.get('barcode',f"MAT-{InventoryMaterial.objects.all().count() + 1}")
                name = data.get('name')
                group = InventoryGroup.objects.get(id=data.get('group'))
                reorder_qty = data.get('reorder_qty')
                value = data.get('value')
                is_billable = data.get('is_billable', False)


                # check name and barcode
                if InventoryMaterial.objects.filter(name=name).exists():
                    success_response['status_code'] = 400
                    success_response['message'] = "Material Name Already Exists"
                elif InventoryMaterial.objects.filter(barcode=barcode).exists():
                    success_response['status_code'] = 400
                    success_response['message'] = "Material Barcode Already Exists"
                else:
                    InventoryMaterial.objects.create(
                        barcode=barcode,
                        name=name,
                        group=group,
                        reorder_qty=reorder_qty,
                        value=value,
                        is_billable=is_billable
                    )
                    success_response['message'] = "Material Created Successfully"

            elif module == 'supplier':
                supplier_name = data.get('supplier_name')
                contact_person = data.get('contact_person')
                supplier_address = data.get('supplier_address')
                supplier_phone = data.get('supplier_phone')
                supplier_email = data.get('supplier_email')
                Supplier.objects.create(supplier_name=supplier_name, contact_person=contact_person, supplier_address=supplier_address, supplier_phone=supplier_phone, supplier_email=supplier_email)
                success_response['message'] = "Supplier Created Successfully"

            elif module == 'grn':
                try:
                    supplier = Supplier.objects.get(id=data.get('supplier'))
                    grn_date = data.get('grn_date')
                    remarks = data.get('remarks')
                    grn_type = data.get('grn_type')
                    created_by = User.objects.get(id=data.get('created_by'))
                    location = Location.objects.get(pk=data.get('location'))
                    grn = Grn.objects.create(
                        supplier=supplier, 
                        grn_date=grn_date, 
                        remarks=remarks, 
                        grn_type=grn_type, 
                        created_by=created_by,
                        total_amount=0,
                        total_qty=0,
                        grn_no = f"GRN-{Grn.objects.all().count() + 1}",
                        location=location
                        )
                    total_amount = 0
                    total_qty = 0
                    for transaction in data.get('transactions'):
                        material = InventoryMaterial.objects.get(barcode=transaction.get('barcode'))
                        barcode = transaction.get('barcode')
                        name = transaction.get('name')
                        amount = transaction.get('amount')
                        pack_qty = transaction.get('pack_qty')
                        uom = transaction.get('uom')
                        rate = transaction.get('rate')
                        qty = transaction.get('qty')
                        total_qty = Decimal(qty) * Decimal(pack_qty)
                        GrnTransaction.objects.create(
                            grn=grn, 
                            material=material, 
                            barcode=barcode, 
                            name=name, 
                            amount=amount, 
                            pack_qty=pack_qty, 
                            uom=uom, 
                            rate=rate, 
                            qty=qty, 
                            total_qty=total_qty)
                        total_amount += Decimal(amount)
                        total_qty += Decimal(total_qty)

                    grn.total_amount = total_amount
                    grn.total_qty = total_qty
                    grn.save()
                        
                    success_response['message'] = "GRN Created Successfully"
                except Exception as e:
                    # Roll back any GRN transactions created
                    if 'grn' in locals():
                        GrnTransaction.objects.filter(grn=grn).delete()
                        grn.delete()
                    success_response['status_code'] = 400
                    success_response['message'] = f"Error on line {sys.exc_info()[2].tb_lineno}: {e}"
                
            elif module == 'issue':
                next_no = Issue.objects.all().last()
                if Issue.objects.all().count() > 0:
                    issue_no = f"IS-{next_no.id + 1}"
                else:
                    issue_no = f"IS-1"
                try:
                    contractor = Contractor.objects.get(id=data.get('contractor'))
                    issue_date = data.get('issue_date')
                    remarks = data.get('remarks')
                    issue_type = data.get('issue_type')
                    created_by = User.objects.get(id=data.get('created_by'))
                    car_no = data.get('car_no')
                    loc_id = data.get('loc_id')
                    location = Location.objects.get(pk=loc_id) if loc_id else Location.objects.get(loc_id='002')
                        
                    issue = Issue.objects.create(
                        contractor=contractor,
                        issue_date=issue_date,
                        remarks=remarks,
                        issue_type=issue_type,
                        created_by=created_by,
                        issue_no=issue_no,
                        car_no=car_no,
                        location=location
                    )
                    total_amount = 0
                    total_qty = 0
                    for transaction in data.get('transactions'):
                        material = InventoryMaterial.objects.get(barcode=transaction.get('barcode'))
                        barcode = transaction.get('barcode')
                        name = transaction.get('name')
                        amount = transaction.get('amount')
                        pack_qty = transaction.get('pack_qty')
                        uom = transaction.get('uom')
                        rate = transaction.get('rate')
                        qty = transaction.get('qty')
                        total_qty = Decimal(qty) * Decimal(pack_qty)
                        IssueTransaction.objects.create(
                            issue=issue,
                            material=material,
                            barcode=barcode,
                            name=name,
                            amount=amount,
                            pack_qty=pack_qty,
                            uom=uom,
                            rate=rate,
                            qty=qty,
                            total_qty=total_qty)

                    issue.total_amount = total_amount
                    issue.total_qty = total_qty

                    for meter in data.get('meters'):
                        if Meter.objects.filter(meter_no=meter).exists():
                            # change contractor
                            Meter.objects.filter(meter_no=meter).update(contractor=contractor)
                        else:
                            Meter.objects.create(meter_no=meter, contractor=contractor, created_by=created_by, issue=issue,location=location)

                    issue.save()

                    success_response['message'] = "Issue Created Successfully"
                except Exception as e:
                    # Roll back any Issue transactions created
                    if 'issue' in locals():
                        Issue.objects.filter(issue_no=issue_no).delete()
                        issue.delete()  
                    success_response['status_code'] = 400
                    success_response['message'] = f"Error on line {sys.exc_info()[2].tb_lineno}: {e}"
            
            elif module == 'plot':
                plot_no = data.get('plot-no')
                contractor = Contractor.objects.get(id=data.get('contractor'))
                plot_size = data.get('plot-size')
                created_by = User.objects.get(id=data.get('mypk'))
                Plot.objects.create(plot_no=plot_no, contractor=contractor, plot_size=plot_size,created_by=created_by)
                success_response['message'] = "Plot Created Successfully"

            elif module == 'service_type':
                name = data.get('service_name')
                description = data.get('service_description')
                created_by = User.objects.get(id=data.get('mypk'))
                ServiceType.objects.create(name=name, description=description, created_by=created_by)
                success_response['message'] = "Service Type Created Successfully"

            elif module == 'service':
                code = f"SRV-{Service.objects.all().count() + 1}"
                name = data.get('service_name')
                description = data.get('service_description')
                rate = data.get('service_rate')
                uom = data.get('service_uom')
                created_by = User.objects.get(id=data.get('mypk'))
                Service.objects.create(code=code, name=name, description=description, rate=rate, uom=uom, created_by=created_by)
                success_response['message'] = "Service Created Successfully"

            elif module == 'service_order':
                service_type = ServiceType.objects.get(id=data.get('service-type'))
                service_date = data.get('service-date')
                contractor = Contractor.objects.get(id=data.get('contractor'))
                plot = Plot.objects.get(plot_no=data.get('plot'))
                geo_code = data.get('geo-code')
                customer = data.get('customer')
                customer_no = data.get('customer_no')
                old_meter_no = data.get('old_meter_no')
                new_meter_no = data.get('new_meter_no')
                meter = Meter.objects.get(meter_no=new_meter_no)
                # check if meter belongs to contractor
                if meter.issue.contractor != contractor:
                    raise Exception("Meter Does Not Belong To Contractor")

                # check if meter is already issued
                if meter.is_issued:
                    raise Exception("Meter Already Issued")

                created_by = User.objects.get(id=data.get('mypk'))
                service_order = ServiceOrder.objects.create(service_type=service_type, service_date=service_date, contractor=contractor, plot=plot, geo_code=geo_code, customer=customer, customer_no=customer_no, old_meter_no=old_meter_no, new_meter=meter, created_by=created_by)
                meter.is_issued = True
                meter.service_order = service_order
                meter.save()
                success_response['message'] = "Service Order Created Successfully"

            elif module == 'service_order_item':
                service_order = ServiceOrder.objects.get(id=data.get('order_id'))
                service = Service.objects.get(id=data.get('service_id'))
                quantity = data.get('serv_qty')
                rate = service.rate
                amount = Decimal(quantity) * Decimal(rate)
                ServiceOrderItem.objects.create(service_order=service_order, service=service, quantity=quantity, rate=rate, amount=amount)
                success_response['message'] = "Service Order Item Created Successfully"
                
            elif module == 'material_order_item':
                service_order = ServiceOrder.objects.get(id=data.get('order_id'))
                material = InventoryMaterial.objects.get(id=data.get('material_id'))
                quantity = data.get('mat_qty')
                material_type = data.get('mat_type')
                
                rate = 0
                amount = Decimal(quantity) * Decimal(rate)
                MaterialOrderItem.objects.create(service_order=service_order, material=material, quantity=quantity, rate=rate, amount=amount, material_type=material_type)
                success_response['message'] = "Material Order Item Created Successfully"

            elif module == 'service_order_return':
                service_order = ServiceOrder.objects.get(id=data.get('server_order_id'))
                material = InventoryMaterial.objects.get(id=data.get('material_id'))
                quantity = data.get('ret_qty')
                user = User.objects.get(id=data.get('mypk'))
                ServiceOrderReturns.objects.create(service_order=service_order, material=material, quantity=quantity, created_by=user, modified_by=user)
                success_response['message'] = "Service Order Return Created Successfully"

            elif module == 'service_order_new':
                header = data.get('header')
                mats = data.get('materials')
                services = data.get('services')
                returns = data.get('returns')
                user = User.objects.get(id=header.get('mypk'))

                # print(mats)
                # print(services)
                # print(returns)

                # raise Exception("Test End")

                # print(mats)
                # raise Exception("Test End")

                # validate meter
                new_meter_no = header.get('new_meter_no')
                contractor = Contractor.objects.get(id=header.get('contractor'))
                print(new_meter_no)
                meter = Meter.objects.get(meter_no=header.get('new_meter_no'))



                # check if meter belongs to contractor
                if meter.contractor != contractor:
                    raise Exception("Meter Does Not Belong To Contractor")

                # check if meter is already issued
                if meter.is_issued:
                    raise Exception("Meter Already Issued")



                try:
                    # create service order
                    service_order = ServiceOrder.objects.create(
                        service_type_id=header.get('service_type'),
                        service_date=header.get('service_date'),
                        contractor_id=header.get('contractor'),
                        plot_id=header.get('plot'),
                        geo_code=header.get('cust_code'),
                        customer=header.get('customer'),
                        customer_no=header.get('customer_no'),
                        old_meter_no=header.get('old_meter_no'),
                        new_meter=meter.meter_no,
                        created_by=user,
                        old_meter_no_reading=header.get('old_meter_no_reading'),
                        new_meter_no_reading=header.get('new_meter_no_reading')
                    )

                    # create service order items
                    for service in services:
                        r_service = Service.objects.get(code=service.get('code'))
                        ServiceOrderItem.objects.create(
                            service_order=service_order,
                            service=Service.objects.get(code=service.get('code')),
                            rate=r_service.rate,
                            quantity=service.get('quantity'),
                            amount=Decimal(service.get('quantity')) * Decimal(r_service.rate)
                        )
                    
                    # # create material order items
                    for mat in mats:
                        print(mat)
                        mt = InventoryMaterial.objects.get(barcode=mat.get('barcode'))
                        MaterialOrderItem.objects.create(
                            service_order=service_order,
                            material=InventoryMaterial.objects.get(barcode=mat.get('barcode')),
                            quantity=mat.get('quantity'),
                            material_type='is',
                            rate=mt.value,
                            amount=Decimal(mt.value) * Decimal(mat.get('quantity'))
                        )

                    # # automate materials add
                    # for ret_item in InventoryMaterial.objects.filter(is_return=True):
                    #     try:
                    #         MaterialOrderItem.objects.create(
                    #             service_order=service_order,
                    #             material=ret_item,
                    #             quantity=1,
                    #             material_type='rt',
                    #             rate=ret_item.value,
                    #             amount=Decimal(mt.value) * Decimal(mat.get('quantity'))
                    #         )
                    #     except Exception as e:
                    #         pass
                    
                    # create service order returns
                    for rt in returns:
                        ServiceOrderReturns.objects.create(
                            service_order=service_order,
                            material=InventoryMaterial.objects.get(barcode=rt.get('barcode')),
                            quantity=rt.get('quantity'),
                            created_by=user,
                            modified_by=user
                        )

                    # add automatic returns
                    for ret_item in InventoryMaterial.objects.filter(is_return=True):
                        try:
                            ServiceOrderReturns.objects.create(
                                service_order=service_order,
                                material=ret_item,
                                quantity=1,
                                created_by=user,
                                modified_by=user
                            )
                        except Exception as e:
                            pass

                    

                    meter.is_issued = True
                    meter.service_order = service_order
                    meter.save()

                    success_response['message'] = "Service Order Created Successfully"

                

                except Exception as e:
                    # delete service order if created
                    if 'service_order' in locals():
                        service_order.delete()
                    success_response['status_code'] = 400
                    success_response['message'] = f"Error on line {sys.exc_info()[2].tb_lineno}: {e}"

            elif module == 'redeem':
                

                try:
                    header = data.get('header')
                    transactions = data.get('transactions')

                    contractor = Contractor.objects.get(id=header.get('contractor'))
                    entry_date = header.get('date')
                    user = User.objects.get(pk=header.get('mypk'))
                    remarks = header.get('remarks')
                    typ = header.get('type')
                    entry_no = f"RED-{Reedem.objects.all().last().pk + 1}" if Reedem.objects.all().count() > 0 else "RED-1"


                    entry = Reedem.objects.create(
                        entry_no=entry_no,
                        entry_date=entry_date,
                        contractor=contractor,created_by=user,
                        transaction_type=typ,remarks=remarks
                    )

                    # enter transactions
                    for transaction in transactions:
                        
                        barcode = transaction.get('barcode')
                        mt = InventoryMaterial.objects.get(barcode=barcode)
                        pack_um = transaction.get('pack_um')
                        balance = transaction.get('balance')
                        reason = transaction.get('reason')
                        qty=transaction.get('qty')
                        RedeemTransactions.objects.create(
                            redeem=entry,
                            material=mt,
                            pack_um=pack_um,
                            balance=balance,
                            reason=reason,
                            qty=qty
                        )





                except Exception as e:
                    # delete service order if created
                    if 'entry' in locals():
                        entry.delete()
                    success_response['status_code'] = 400
                    success_response['message'] = f"Error on line {sys.exc_info()[2].tb_lineno}: {e}"

            elif module == 'broadcast':
                target = data.get('target')
                ttype = data.get('type')
                message = data.get('message')

                # Extract text between <> quotes
                import re
                quotes = re.findall(r'>(.*?)<', message)
                if quotes:
                    for quote in quotes:
                        link = shorten_url(quote)
                        message = message.replace(quote, link)
                        message = message.replace(f'>{quote}<', quote)



                total_sms = 0
                total_email = 0

                message = message.replace('<', '')
                message = message.replace('>', '')

                if target == 'contractor':
                    for x_foc in Contractor.objects.all():
                        email = False
                        phone = False
                        company = False



                        email = x_foc.email
                        phone = x_foc.phone
                        company = x_foc.company
                        now_msg = message.replace('$name', f"{company}")


                        print(company,email,phone,now_msg)

                        if ttype == 'sms':
                            Sms.objects.create(
                                api=SmsApi.objects.get(sender_id='SNEDA SSML') if SmsApi.objects.filter(sender_id='SNEDA SSML').exists() else SmsApi.objects.get(is_default=True),
                                to=phone,
                                message=now_msg
                            )

                            total_sms += 1

                        elif ttype == 'email':
                            MailQueues.objects.create(
                                recipient=email,
                                subject=f'SNEDA Broadcast | {company}',
                                body=now_msg,
                                sender=MailSenders.objects.get(address='solomon@snedaghana.com') if MailSenders.objects.filter(address='solomon@snedaghana.com') else MailSenders.objects.get(is_default=True),
                                mail_key=make_md5_hash(f"{email}-{now_msg}{company}")
                            )
                            total_email += 1

                        else:
                            Sms.objects.create(
                                api=SmsApi.objects.get(sender_id='SNEDA SSML') if SmsApi.objects.filter(
                                    sender_id='SNEDA SSML').exists() else SmsApi.objects.get(is_default=True),
                                to=phone,
                                message=now_msg
                            )

                            MailQueues.objects.create(
                                recipient=email,
                                subject='SNEDA Broadcast',
                                body=now_msg,
                                sender=MailSenders.objects.get(
                                    address='solomon@snedaghana.com') if MailSenders.objects.filter(
                                    address='solomon@snedaghana.com') else MailSenders.objects.get(is_default=True),
                                mail_key=make_md5_hash(f"{email}-{now_msg}{company}")
                            )

                            total_sms += 1
                            total_email += 1



                if target == 'staff':
                    # Get users in ssml group
                    if not Group.objects.filter(name='ssml').exists():
                        raise Exception("SSML group does not exist")

                    ssml_group = Group.objects.get(name='ssml')
                    staff_users = ssml_group.user_set.all()

                    if not staff_users:
                        raise Exception("No users found in SSML group")

                    ttype = data.get('type')
                    message = data.get('message')

                    for user in staff_users:
                        email = user.email
                        addon = UserAddOns.objects.get(user=user)
                        phone = addon.phone
                        name = user.get_full_name()
                        msg = message.replace('$name', name)

                        if ttype == 'sms' and phone:
                            phone = phone.replace('233', '0').replace('+233', '0')
                            if len(phone) == 10:
                                Sms.objects.create(
                                    api=SmsApi.objects.get(sender_id='SNEDA SSML') if SmsApi.objects.filter(
                                        sender_id='SNEDA SSML').exists() else SmsApi.objects.get(is_default=True),
                                    to=phone,
                                    message=msg
                                )
                                total_sms += 1

                        elif ttype == 'email' and email:
                            MailQueues.objects.create(
                                recipient=email,
                                subject='SNEDA Broadcast',
                                body=msg,
                                sender=MailSenders.objects.get(
                                    address='solomon@snedaghana.com') if MailSenders.objects.filter(
                                    address='solomon@snedaghana.com') else MailSenders.objects.get(is_default=True),
                                mail_key=make_md5_hash(f"{email}-{msg}{name}")
                            )
                            total_email += 1

                        elif ttype == 'both' and (email or phone):
                            if phone:
                                phone = phone.replace('233', '0').replace('+233', '0')
                                if len(phone) == 10:
                                    Sms.objects.create(
                                        api=SmsApi.objects.get(sender_id='SNEDA SSML') if SmsApi.objects.filter(
                                            sender_id='SNEDA SSML').exists() else SmsApi.objects.get(is_default=True),
                                        to=phone,
                                        message=msg
                                    )
                                total_sms += 1

                            if email:
                                MailQueues.objects.create(
                                    recipient=email,
                                    subject='SNEDA Broadcast',
                                    body=msg,
                                    sender=MailSenders.objects.get(
                                        address='solomon@snedaghana.com') if MailSenders.objects.filter(
                                        address='solomon@snedaghana.com') else MailSenders.objects.get(is_default=True),
                                    mail_key=make_md5_hash(f"{email}-{msg}{name}")
                                )
                                total_email += 1


                success_response['message'] = f"Broadcast sent to {target} with {ttype} type. Total SMS: {total_sms}. Total Email: {total_email}"

            elif module == 'transfer':
                hdd = data.get('header')
                print(hdd)
                transactions = data.get('transactions')

                entry_date = hdd.get('entry_date')
                loc_from = hdd.get('loc_from')
                loc_to = hdd.get('loc_to')
                mypk = hdd.get('mypk')
                remarks = hdd.get('remarks')
                tran_type = hdd.get('tran_type')

                if loc_from == loc_to:
                    raise Exception("Location from and to cannot be same")

                owner = User.objects.get(pk=mypk)
                loc_fr = Location.objects.get(pk=loc_from)
                loc_t = Location.objects.get(pk=loc_to)

                try:
                
                    next_no = TransferHd.objects.all().last().pk + 1 if TransferHd.objects.all().count() > 0 else 1

                    from datetime import datetime

                    entry_date_str = hdd.get('entry_date')  # e.g. "2025-10-02"

                    # Convert string to datetime (assuming format YYYY-MM-DD)
                    entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d").date()

                    # Extract month and day
                    month = entry_date.month
                    day = entry_date.day

                    # Add month and year to entry_no
                    entry_no = f'TR{month}{day}-{next_no}'

                    print(entry_no)


                    TransferHd.objects.create(
                        loc_fr=loc_fr,
                        loc_to=loc_t,
                        entry_date=entry_date,
                        remarks=remarks,
                        created_by=owner,
                        tran_type=tran_type,
                        entry_no=entry_no
                    )

                    hd = TransferHd.objects.get(entry_no=entry_no)

                    for transaction in transactions:
                        print(transaction)
                        mt = InventoryMaterial.objects.get(barcode=transaction.get('barcode'))


                        if TransferTr.objects.filter(entry=hd, material=mt).exists():
                            pass
                        else:

                            TransferTr.objects.create(
                                entry=hd,
                                material=mt,
                                name=mt.name,
                                barcode=mt.barcode,
                                oum=transaction.get('oum'),
                                pack_qty=transaction.get('pack_qty'),
                                sent_qty=transaction.get('sent_qty')
                            )

                    
                    success_response['message'] = "Transfer Created Successfully"
                    success_response['status_code'] = 200

                    
                    # todo: save tran hd
                
                except Exception as e:
                    # If TransferHd was created, delete it to avoid orphaned header
                    try:
                        if 'hd' in locals() and isinstance(hd, TransferHd):
                            hd.delete()
                    except Exception:
                        pass
                    success_response['status_code'] = 400
                    success_response['message'] = f"Error on line {sys.exc_info()[2].tb_lineno}: {e}"


            else:
                success_response['status_code'] = 400
                success_response['message'] = f"Module Not Found"



        elif method == 'VIEW':

                if module == 'contractor':
                    id = data.get('id','*')
                    if id == '*':
                        contractors = Contractor.objects.all().order_by('company')
                        success_response['message'] = [contractor.obj() for contractor in contractors]


                        # success_response['message'] = [foc.obj() for foc in contractors if
                        #                                foc.is_complied().get('status')]
                    else:
                        contractor = Contractor.objects.get(id=id)
                        success_response['message'] = contractor.obj()

                elif module == 'foc_compliance':
                    success_response['message'] = [x.obj() for x in FocCompliance.objects.all()]
                    success_response['statuc_code'] = 200

                elif module == 'export_meters':
                    import openpyxl
                    book = openpyxl.Workbook()
                    sheet = book.active
                    hd = ['STS','PHASE','DATE ADDED']
                    sheet.append(hd)
                    for meter in Meter.objects.all():
                        sheet.append([
                            meter.meter_no,
                            meter.linked_phase.description if meter.linked_phase else "Not Set",
                            str(meter.created_at)
                        ])

                    import uuid
                    file_name = f"static/tmp/{uuid.uuid4().hex}.xlsx"
                    book.save(file_name)
                    success_response['message'] = file_name

                elif module == 'foc_mis':
                    from datetime import datetime
                    import calendar
                    from django.db.models import Sum
                    from fpdf import FPDF
                    import uuid
                    import zipfile
                    import os

                    target_date_str = data.get('target_date')
                    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()

                    # First day of the month
                    start_date = target_date.replace(day=1)

                    # Last day of the month
                    last_day = calendar.monthrange(target_date.year, target_date.month)[1]
                    end_date = target_date.replace(day=last_day)

                    # get all invoices range
                    fq = FocInvoiceHd.objects.filter(invoice_date__gte=start_date, invoice_date__lte=end_date).order_by('invoice_date')
                    gross_total = fq.aggregate(Sum('gross_amount'))['gross_amount__sum'] or 0
                    taxable_total = fq.aggregate(Sum('taxable_amount'))['taxable_amount__sum'] or 0
                    tax_total = fq.aggregate(Sum('tax_amount'))['tax_amount__sum'] or 0
                    wht_total = fq.aggregate(Sum('wht_amount'))['wht_amount__sum'] or 0
                    net_total = fq.aggregate(Sum('net_amount'))['net_amount__sum'] or 0
                    service_total = fq.aggregate(Sum('service_charge'))['service_charge__sum'] or 0

                    success_response['message'] = [fi.obj() for fi in fq]
                    success_response['gross_amount'] = gross_total
                    success_response['taxable_amount'] = taxable_total
                    success_response['tax_amount'] = tax_total
                    success_response['wht_amount'] = wht_total
                    success_response['net_amount'] = net_total
                    success_response['service_charge'] = service_total

                    # 1. Generate ZIP of all individual invoices
                    zip_file_name = f"{uuid.uuid4().hex[:6]}_invoices.zip"
                    zip_file_path = f"static/tmp/{zip_file_name}"

                    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for finv in fq:
                            invoice_file_name = finv.obj().get('invoice')
                            if invoice_file_name:
                                invoice_full_path = f"static/tmp/{invoice_file_name}"
                                if os.path.exists(invoice_full_path):
                                    zf.write(invoice_full_path, arcname=invoice_file_name)

                    success_response['bundle'] = zip_file_path

                    # 2. Generate Professional Summary PDF
                    class MISPDF(FPDF):
                        def header(self):
                            logo_path = 'static/general/logo.png'
                            if os.path.exists(logo_path):
                                self.image(logo_path, 10, 10, 35)

                            self.set_font('Arial', 'B', 16)
                            self.set_text_color(44, 62, 80)
                            self.set_xy(50, 10)
                            self.cell(0, 10, COMPANY_DETAILS.get('name'), 0, 1, 'L')

                            self.set_font('Arial', '', 9)
                            self.set_text_color(100, 100, 100)
                            self.set_x(50)
                            self.cell(0, 4, COMPANY_DETAILS.get('address'), 0, 1, 'L')
                            self.set_x(50)
                            self.cell(0, 4, f"{COMPANY_DETAILS.get('email')} | {COMPANY_DETAILS.get('phone')}" , 0, 1, 'L')

                            self.ln(10)
                            self.set_draw_color(44, 62, 80)
                            self.line(10, 35, 200, 35)
                            self.ln(5)

                        def footer(self):
                            self.set_y(-15)
                            self.set_font('Arial', 'I', 8)
                            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

                    pdf = MISPDF()
                    pdf.set_auto_page_break(auto=True, margin=15)
                    pdf.add_page()

                    # Report Title & Period
                    pdf.set_font('Arial', 'B', 14)
                    pdf.set_text_color(0, 0, 0)
                    pdf.cell(0, 10, 'MONTHLY INVOICE SUMMARY REPORT', 0, 1, 'C')
                    pdf.set_font('Arial', '', 10)
                    pdf.cell(0, 5, f"Period: {start_date.strftime('%d %b, %Y')} to {end_date.strftime('%d %b, %Y')}", 0, 1, 'C')
                    pdf.ln(10)

                    # Summary Metrics (Styled like the Dashboard Cards)
                    pdf.set_fill_color(248, 249, 250)
                    pdf.set_draw_color(227, 230, 240)

                    card_w = 45
                    gap = 2.5
                    curr_x = 10
                    curr_y = pdf.get_y()

                    metrics = [
                        ("Gross Amount", gross_total, (0,0,0)),
                        ("Admin Fee", service_total, (23, 162, 184)),
                        ("WHT (5%)", wht_total, (220, 53, 69)),
                        ("Net Amount", net_total, (40, 167, 69))
                    ]

                    for title, val, color in metrics:
                        pdf.rect(curr_x, curr_y, card_w, 22, 'FD')
                        pdf.set_xy(curr_x, curr_y + 3)
                        pdf.set_font('Arial', 'B', 8)
                        pdf.set_text_color(100, 100, 100)
                        pdf.cell(card_w, 5, title.upper(), 0, 1, 'C')

                        pdf.set_xy(curr_x, curr_y + 10)
                        pdf.set_font('Arial', 'B', 12)
                        pdf.set_text_color(*color)
                        pdf.cell(card_w, 10, f"{val:,.2f}", 0, 1, 'C')
                        curr_x += card_w + gap

                    pdf.set_xy(10, curr_y + 30)
                    pdf.set_text_color(0, 0, 0)

                    # Detailed Table
                    pdf.set_font('Arial', 'B', 10)
                    pdf.set_fill_color(44, 62, 80)
                    pdf.set_text_color(255, 255, 255)

                    pdf.cell(10, 10, 'NO', 1, 0, 'C', True)
                    pdf.cell(55, 10, ' CONTRACTOR', 1, 0, 'L', True)
                    pdf.cell(30, 10, 'GROSS AMT', 1, 0, 'R', True)
                    pdf.cell(30, 10, 'ADMIN FEE', 1, 0, 'R', True)
                    pdf.cell(30, 10, 'WHT (5%)', 1, 0, 'R', True)
                    pdf.cell(35, 10, 'NET AMT', 1, 1, 'R', True)

                    pdf.set_font('Arial', '', 8)
                    pdf.set_text_color(0, 0, 0)

                    for i, finv in enumerate(fq, 1):
                        # Main Invoice Row
                        pdf.set_font('Arial', 'B', 8)
                        pdf.cell(10, 8, str(i), 1, 0, 'C')

                        pdf.set_font('Arial', '', 8)
                        pdf.cell(55, 8, f" {str(finv.foc.company)[:25]}", 1, 0, 'L')
                        pdf.cell(30, 8, f"{finv.gross_amount:,.2f}", 1, 0, 'R')
                        pdf.cell(30, 8, f"{finv.service_charge:,.2f}", 1, 0, 'R')
                        pdf.cell(30, 8, f"{finv.wht_amount:,.2f}", 1, 0, 'R')
                        pdf.set_font('Arial', 'B', 8)
                        pdf.cell(35, 8, f"{finv.net_amount:,.2f}", 1, 1, 'R')

                        # Bank details row
                        curr_y = pdf.get_y()
                        pdf.set_font('Arial', 'I', 7)
                        pdf.set_text_color(80, 80, 80)
                        pdf.set_fill_color(252, 252, 252)
                        bank_info = f"BANK DETAILS: {finv.foc.bank_name or 'N/A'} | A/C: {finv.foc.bank_acct_number or 'N/A'} | BRANCH: {finv.foc.bank_branch or 'N/A'}"
                        pdf.cell(10, 6, '', 1, 0, 'C', True)
                        pdf.rect(13, curr_y + 1, 4, 4)
                        pdf.cell(180, 6, f" {bank_info}", 1, 1, 'L', True)
                        pdf.set_font('Arial', '', 8)
                        pdf.set_text_color(0, 0, 0)

                    # Total Row
                    pdf.set_font('Arial', 'B', 9)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.cell(65, 10, 'TOTALS', 1, 0, 'R', True)
                    pdf.cell(30, 10, f"{gross_total:,.2f}", 1, 0, 'R', True)
                    pdf.cell(30, 10, f"{service_total:,.2f}", 1, 0, 'R', True)
                    pdf.cell(30, 10, f"{wht_total:,.2f}", 1, 0, 'R', True)
                    pdf.set_text_color(40, 167, 69)
                    pdf.cell(35, 10, f"{net_total:,.2f}", 1, 1, 'R', True)




                    # Approvals Sections
                    pdf.ln(15)
                    y_sign = pdf.get_y()
                    if y_sign > 230: # Check for page break before signatures
                        pdf.add_page()
                        y_sign = pdf.get_y()

                    def draw_sign_block(x, title):
                        pdf.set_xy(x, y_sign)
                        pdf.set_font('Arial', 'B', 9)
                        pdf.set_text_color(44, 62, 80)
                        pdf.cell(60, 7, title, 0, 1, 'L')
                        pdf.set_draw_color(200, 200, 200)
                        pdf.line(x, y_sign + 7, x + 55, y_sign + 7)

                        pdf.set_font('Arial', '', 8)
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_xy(x, y_sign + 10)
                        pdf.cell(60, 6, "Name: __________________________", 0, 1, 'L')
                        pdf.set_x(x)
                        pdf.cell(60, 6, "Position: _______________________", 0, 1, 'L')
                        pdf.set_x(x)
                        pdf.cell(60, 6, "Date: __________________________", 0, 1, 'L')
                        pdf.set_x(x)
                        pdf.cell(60, 10, "Sign: __________________________", 0, 1, 'L')

                    draw_sign_block(10, "PREPARED BY")
                    draw_sign_block(75, "VERIFIED BY")
                    draw_sign_block(140, "APPROVED BY")

                    summary_pdf_name = f"mis_summary_{uuid.uuid4().hex[:6]}.pdf"
                    summary_pdf_path = f"static/tmp/{summary_pdf_name}"
                    pdf.output(summary_pdf_path)

                    success_response['pdf'] = summary_pdf_path





                elif module == 'foc_compliance_type':
                    success_response['message'] = [ct.obj() for ct in FocComplianceType.objects.all().order_by('name')]

                elif module == 'ledger':
                    success_response['message'] = [ledge.obj() for ledge in AccountLedger.objects.all()]

                elif module == 'jv':
                    entry_no = data.get('entry_no','*')
                    success_response['message'] = [jv.obj() for jv in JournalVoucherHd.objects.all()] if entry_no == '*' else [jv.obj() for jv in JournalVoucherHd.objects.filter(entry_no=entry_no)]

                elif module == 'print_petty_cash':
                    from fpdf import FPDF
                    import datetime

                    class PettyCashPDF(FPDF):
                        def header(self):
                            # Logo (ensure this path is correct in your project)
                            self.image('static/general/logo.png', 10, 8, 33)
                            self.set_font('Arial', 'B', 16)
                            self.cell(0, 12, 'PETTY CASH VOUCHER', ln=True, align='C')
                            self.ln(2)

                        def footer(self):
                            # Position 50 units from bottom
                            self.set_y(-50)
                            page_width = self.w - 20
                            cell_w = page_width / 4
                            self.set_font('Arial', '', 10)
                            y = self.get_y()

                            # Header row for signatories
                            self.cell(cell_w, 6, 'Prepared By', align='C', border=0)
                            self.cell(cell_w, 6, "Receiver's Signature", align='C', border=0)
                            self.cell(cell_w, 6, 'Checked by / Dept. Head', align='C', border=0)
                            self.cell(cell_w, 6, 'Authorised Signatory', align='C', border=0)
                            self.ln(12)

                            # Draw signature lines
                            sig_line_length = cell_w - 10
                            line_y = self.get_y()
                            x = 10
                            for _ in range(4):
                                self.line(x, line_y, x + sig_line_length, line_y)
                                x += cell_w
                            self.ln(10)

                    entry_no = data.get('entry_no')
                    petty = PettyCash.objects.get(entry_no=entry_no)
                    rows = list(Expense.objects.filter(entry_no=entry_no).order_by('id'))



                    pdf = PettyCashPDF()
                    pdf.add_page()
                    th = pdf.font_size_pt * 0.6 + 1

                    # Top Info: Paid to, Voucher No., Dept, Date
                    pdf.set_font('Arial', '', 11)
                    left_x = 12
                    col_margin = 100

                    y = pdf.get_y()
                    pdf.set_xy(left_x, y)
                    pdf.cell(24, 7, 'Paid to:', 0, 0)
                    pdf.set_font('Arial', 'U', 11)
                    pdf.cell(64, 7, '', 0, 0)
                    pdf.set_font('Arial', '', 11)
                    pdf.cell(10, 7, '', 0, 0)
                    pdf.cell(22, 7, 'Voucher No.:', 0, 0)
                    pdf.set_font('Arial', 'U', 11)
                    pdf.cell(30, 7, str(petty.entry_no), 0, 1)
                    pdf.set_font('Arial', '', 11)

                    y = pdf.get_y()
                    pdf.set_xy(left_x, y)
                    pdf.cell(24, 7, 'Dept:', 0, 0)
                    pdf.set_font('Arial', 'U', 11)
                    pdf.cell(64, 7, '', 0, 0)
                    pdf.set_font('Arial', '', 11)
                    pdf.cell(10, 7, '', 0, 0)
                    pdf.cell(22, 7, 'Date:', 0, 0)
                    pdf.set_font('Arial', 'U', 11)
                    date_str = petty.date.strftime("%d/%m/%y") if petty.date else ''
                    pdf.cell(30, 7, date_str, 0, 1)
                    pdf.ln(3)

                    # Table header
                    pdf.set_font('Arial', 'B', 11)
                    col_widths = [15, 105, 40]
                    pdf.cell(col_widths[0], th * 1.4, 'Sr. No.', border=1, align='C')
                    pdf.cell(col_widths[1], th * 1.4, 'PARTICULARS', border=1, align='C')
                    pdf.cell(col_widths[2], th * 1.4, 'AMOUNT GHS', border=1, ln=1, align='C')

                    # Table rows, support multi-page output
                    pdf.set_font('Arial', '', 11)
                    total_amt = 0.0
                    for idx, txn in enumerate(rows):
                        sr = str(idx+1)
                        particulars = str(txn.description)
                        amount = "{:.2f}".format(float(txn.amount))

                    file_name = f'static/general/tmp/{entry_no}.pdf'
                    pdf.output(file_name)

                    success_response['message'] = file_name


                elif module == 'export_petty_cash':
                    entry_no = data.get('entry_no')
                    import openpyxl
                    book = openpyxl.Workbook()
                    sheet = book.active
                    sheet.title = "Transactions"

                    sheet.append([
                        "DIRECTION","CATEGORY","TYPE","DATE","REFERENCE","DESCRIPTION","AMOUNT","EVIDENCE"
                    ])

                    for transaction in Expense.objects.filter(entry_no=entry_no):
                        evidence = transaction.evidence()
                        x_file = ""
                        if len(evidence) > 0:
                            lx = evidence.split(',')

                            for lu in lx:
                                file = lu.split('|')[-1].lstrip('/')
                                file_url = f"{BASE_URL}{file}"
                                short_link = shorten_url(file_url)
                                x_file += f"{short_link},"

                            x_file = x_file.rstrip(',')
                            print(x_file)
                        li = [transaction.direction,transaction.category,transaction.transaction_type,transaction.date,transaction.reference,transaction.description,transaction.amount,x_file]
                        sheet.append(li)

                    import uuid
                    unique_id = uuid.uuid4()
                    filename = f"static/general/tmp/petty_cash_{unique_id}.xlsx"
                    book.save(filename)
                    success_response['message'] = filename


                elif module == 'retired_meters':
                    pk = data.get('pk','*')
                    if pk == '*':
                        success_response['message'] = [ret.obj() for ret in RetiredMetersBox.objects.all()]
                    else:
                        success_response['message'] = [ret.obj() for ret in RetiredMetersBox.objects.filter(pk=pk)]

                elif module == 'installed_meters':
                    start_date = data.get('start_date')
                    end_date = data.get('end_date')
                    import openpyxl
                    book = openpyxl.Workbook()
                    sheet = book.active
                    sheet.title = 'INSTALLATIONS'
                    sheet.append(["SERVICE TYPE","INSTALLATION TYPE","SERVICE DATE","FOC","SPN","FINAL READINGS","NEW METER","OLD METER"])
                    for service in ServiceOrder.objects.filter(service_date__gte=start_date, service_date__lte=end_date):
                        print(service)
                        li = [
                            service.service_type.name,
                            service.installation_type.name if service.installation_type else 'unknown',
                            service.service_date,
                            service.contractor.company,
                            service.spn,
                            service.final_readings,
                            service.new_meter,
                            service.old_meter_no
                            ]
                        sheet.append(li)

                    import uuid
                    unique_id = uuid.uuid4()
                    filename = f"static/general/tmp/installations_{unique_id}_{start_date}_to_{end_date}.xlsx"
                    book.save(filename)
                    success_response['message'] = {
                        # "json":[serv.obj() for serv in ServiceOrder.objects.filter(service_date__gte=start_date, service_date__lte=end_date)],
                        "file":filename
                        }

                elif module == 'month_inv_report':
                    start_date = data.get('start_date')
                    end_date = data.get('end_date')
                    for_invoice = data.get('for_invoice')

                    print(data)
                    import openpyxl
                    book = openpyxl.Workbook()

                    print("Updating Returns...")
                    rr = 1
                    all_ct = RetiredMetersTransactions.objects.filter(date_removed__gte=start_date,date_removed__lte=end_date).count()
                    for rt in RetiredMetersTransactions.objects.filter(date_removed__gte=start_date,date_removed__lte=end_date):
                        spn = rt.spn
                        rrm = f"{rr} / {all_ct}"
                        try:
                            service = ServiceOrder.objects.get(spn=spn)
                            rt.foc = service.contractor
                            rt.gps_address = service.gps_code
                            rt.installation_type = service.installation_type.name if service.installation_type else 'NONE'
                            rt.save()
                            print(rrm, rt.box.box_no, "-", rt.sn, "Updated",service.installation_type.name if service.installation_type else 'NONE')

                        except Exception as e:
                            print(rrm, rt.box.box_no, "-", rt.sn, "Err: ", str(e))
                        rr += 1

                    if for_invoice == 'YES':

                        from datetime import datetime

                        days_count = 1
                        if start_date and end_date:
                            try:
                                fmt = "%Y-%m-%d"
                                d1 = datetime.strptime(start_date, fmt)
                                d2 = datetime.strptime(end_date, fmt)
                                days_count = (d2 - d1).days
                            except Exception:
                                days_count = 1



                        foc_summ = book.active
                        foc_summ.title = "1.2 Summary FOC"
                        foc_sum_hd = ["No","Contractor","Total"]
                        for so in InstallationType.objects.all().order_by('name'):
                            foc_sum_hd.append(so.name)
                        foc_summ.append(foc_sum_hd)

                        fosn = 1
                        print("FOC SUMMARY....")
                        for foc in Contractor.objects.filter(is_installer=True).order_by('company'):
                            total_jobs = ServiceOrder.objects.filter(ecg_date__gte=start_date,ecg_date__lte=end_date,contractor=foc,flag_for_invoice=True).count()

                            if total_jobs > 0:
                                li = [fosn,foc.company,total_jobs]
                                for so in InstallationType.objects.all().order_by('name'):

                                    this_total = ServiceOrder.objects.filter(ecg_date__gte=start_date,ecg_date__lte=end_date,contractor=foc,installation_type=so,flag_for_invoice=True).count()

                                    print(foc.company,so.name,this_total)
                                    print("--------------------------------")
                                    li.append(this_total)

                                foc_summ.append(li)
                                fosn += 1



                        sheet = book.create_sheet(title = "Installations")

                        print("INSTALLATIONS")
                        sheet.append(["DATE","METER","OLD METER","SPN","JOB TYPE","FOC"])
                        for service in ServiceOrder.objects.filter(ecg_date__gte=start_date,ecg_date__lte=end_date,flag_for_invoice=True):
                            sheet.append([service.ecg_date,service.new_meter,service.old_meter_no,service.spn,service.service_type.name,service.contractor.company])
                            # print(service.service_type.name)
                            # if service.service_type.name in ['Replacement', 'Regularization']:

                            #     if service.is_boxed:
                            #         print(f"BOXING EXPECTED FOR {service.service_type.name} and FOUND")
                            #         sheet.append([service.ecg_date,service.new_meter,service.old_meter_no,service.spn,service.service_type.name,service.contractor.company])
                            #     else:
                            #         print(f"BOXING EXPECTED FOR {service.service_type.name} and NOT FOUND")
                            # else:

                            #     print(f"BOXING NOT EXPECTED FOR {service.service_type.name}")
                            #     sheet.append([service.ecg_date,service.new_meter,service.old_meter_no,service.spn,service.service_type.name,service.contractor.company])

                            # print("--------------------------------")


                        # summary consumption
                        mcs = book.create_sheet(title="Consumption Summary")
                        print("Consumption Summary")
                        mcs.append(["ITEM NAME","UNIT","CONCUMNED","WASTAGE","WASTAGE QTY","TOTAL CONSUMPTION","AVG CONSUMPTION"])
                        for mat in InventoryMaterial.objects.all():
                            from django.db.models import Sum



                            consumned = MaterialOrderItem.objects.filter(
                                service_order__ecg_date__gte=start_date,
                                service_order__ecg_date__lte=end_date,
                                material=mat,
                                service_order__flag_for_invoice=True
                            ).aggregate(total_quantity=Sum('quantity'))['total_quantity'] or 0

                            if consumned > 0:

                                mcs.append(
                                    [mat.name,"",consumned,"","",consumned,Decimal(consumned)/Decimal(days_count)]
                                )

                        ## create material consumption

                        ms = book.create_sheet(title="3.2 Material Consumption")
                        print("Materials Consumption")
                        hd = ["SN","DISTRICT","FOC","SPN","INSTALL DATE","METER TYPE","GPS","INSTALLATION TYPE"]
                        for mtn in InventoryMaterial.objects.filter(is_issue=True).order_by('name'):
                            hd.append(mtn.name)
                        hd.append('Tower Clip (if used)')
                        hd.append('Input Meter STS number')
                        hd.append('Meter Enclosure used?')
                        hd.append('Colours of Meter Seal Installed')

                        ms.append(hd)
                        sn = 1
                        for service in ServiceOrder.objects.filter(ecg_date__gte=start_date,ecg_date__lte=end_date,flag_for_invoice=True):

                            # check if old meter is boxed

                            if True:

                                phase = Meter.objects.get(meter_no=service.new_meter).phase if Meter.objects.filter(meter_no=service.new_meter).exists() else "Unknown"
                                line = [
                                    sn,
                                    service.location.loc_name,
                                    service.contractor.company,
                                    service.spn,
                                    service.ecg_date,
                                    service.meter_phase(),
                                    service.gps_code,
                                    service.service_type.name
                                ]

                                for mtn in InventoryMaterial.objects.filter(is_issue=True).order_by('name'):
                                    used_qty = MaterialOrderItem.objects.filter(material=mtn,service_order=service).aggregate(total=Sum('quantity'))['total'] or 0
                                    line.append(used_qty)

                                line.append("YES")
                                line.append(service.new_meter)
                                line.append("YES")

                                line.append("BLUE")
                                ms.append(line)
                                sn += 1


                        # service count
                        sc = book.create_sheet(title="Count By Service")
                        print("Service Count")
                        sc.append(["NAME","TOTAL"])
                        for st in ServiceType.objects.all():
                            name = st.name
                            total = ServiceOrder.objects.filter(ecg_date__gte=start_date,ecg_date__lte=end_date,service_type=st,flag_for_invoice=True).count()
                            if total > 0:
                                sc.append([name,total])

                        # 3.3 Material Inventory Reciept
                        mir = book.create_sheet(title="3.3 Inventory Reciept")
                        print("Inventory Reciept")
                        from datetime import date, timedelta
                        mirhd = ["No","Material Description","Unit of Measurement","Total Request"]

                        months_data = []
                        from datetime import datetime, date

                        start_year = 2025
                        start_month = 1  # January

                        if isinstance(end_date, str):
                            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

                        # Build a list of (year, month) tuples from Jan 2025 → end_date
                        current = date(start_year, start_month, 1)
                        end_of_range = date(end_date.year, end_date.month, 1)

                        while current <= end_of_range:
                            start_date_of_month = current
                            year = current.year
                            month = current.month

                            if month == 12:
                                next_month = date(year + 1, 1, 1)
                            else:
                                next_month = date(year, month + 1, 1)

                            # --- your existing logic using start_date_of_month and next_month ---

                            # Advance to next month
                            if month == 12:
                                current = date(year + 1, 1, 1)
                            else:
                                current = date(year, month + 1, 1)
                            end_date_of_month = next_month - timedelta(days=1)
                            month_name_yy = start_date_of_month.strftime("%b'%y")  # e.g. Jun'24
                            lx = [start_date_of_month,end_date_of_month,month_name_yy]
                            months_data.append({
                                'start':start_date_of_month,
                                'end':end_date_of_month,
                                'name':month_name_yy
                            })
                            mirhd.append(month_name_yy)
                        mirhd.append("Total Receipts from ECG")
                        mirhd.append("Balance to be Received from ECG")

                        mir.append(mirhd)

                        mirsn = 1
                        for mirmat in InventoryMaterial.objects.filter(is_issue=True):
                            total_request = mirmat.required_qty
                            legend_recieved = 0
                            li = [mirsn,mirmat.name,mirmat.uom,total_request]
                            print(months_data)
                            for mt in months_data:
                                print(mt)
                                total_recieved = mirmat.in_by_date_range(mt.get('start'),mt.get('end'))
                                li.append(total_recieved)
                                legend_recieved += total_recieved

                            li.append(legend_recieved)
                            li.append(total_request-legend_recieved)
                            mir.append(li)
                            mirsn += 1


                        # 3.4 Inventory Tracking
                        itr = book.create_sheet(title="3.4 Inventory Tracking")
                        print("Inventory Tracking")
                        itrhd = ["No","Material Description","UNIT","TOTAL RECIEPT"]
                        for mt in months_data:
                            itrhd.append(mt.get('name'))
                        itrhd.append("Total Utilized by FOCs")
                        itrhd.append("Stock Balance with Supplier")
                        itr.append(itrhd)
                        mirsn = 1
                        from datetime import date

                        first_day = date(2025, 1, 1)

                        for mirmat in InventoryMaterial.objects.filter(is_issue=True):
                            total_recieved =  mirmat.in_by_date_range(first_day,data.get('end_date'))
                            legend_usage = 0

                            li = [mirsn,mirmat.name,mirmat.uom,total_recieved]

                            print(months_data)
                            for mt in months_data:
                                print(mt)
                                total_used = mirmat.used_by_date_range(mt.get('start'),mt.get('end'),False)
                                li.append(total_used)
                                legend_usage += total_used

                            li.append(legend_usage)
                            li.append(total_recieved-legend_usage)
                            itr.append(li)
                            mirsn += 1

                        #4.1 Summary_Retired Materials
                        srm_sheet = book.create_sheet(title='4.1 Summary Retired Materials')
                        print("Retired Materials Summary")
                        srm_hd = ["No","Disctict","Energy Meter","Meter Enclosure","MCB/ MCCB/ FUSE","Cables etc","Burnt Meters","Stolen Meters"]
                        srm_sheet.append(srm_hd)


                        risn = 1
                        end_date = data.get('end_date')
                        start_date = data.get('start_date')

                        for loc in Location.objects.all():

                            total_removed_meters = RetiredMetersTransactions.objects.filter(date_removed__gte=start_date,date_removed__lte=end_date,box__location=loc).count()
                            print(start_date,"to",end_date)
                            if total_removed_meters > 0:
                                ri = [risn,loc.loc_name,total_removed_meters]

                                srm_sheet.append(ri)
                                risn += 1


                        # 4.2 Retiring Material
                        rm_sheet = book.create_sheet("4.2 Retiring Material")
                        print("Retiring Materials")
                        rm_hd = ["No","Disctrict","FOC Company Name","SPN","OLD METER NUMBER","Meter Phase(1Ø/3Ø)",
                        "Meter Year of Manufacturing",
                        "GPS/Digital Address",
                        "Installation Type",
                        "Meter Display ON/OFF",
                        "Faulty Meter Make (To be Replaced)",
                        "MCB/ MCCB/ FUSE Retired?(Yes/No)",
                        " Meter Enclosure Retired?(Yes/No)",
                        "Length of existing cable retired (in meters)"
                        ]

                        rm_sheet.append(rm_hd)

                        rmline = 1
                        for loc in Location.objects.all():
                            removed = RetiredMetersTransactions.objects.filter(date_removed__gte=start_date,date_removed__lte=end_date,box__location=loc)
                            if removed.count() > 0:
                                for rem in removed:
                                    li = [rmline,loc.loc_name,rem.foc.company,rem.spn,rem.old_meter_no,rem.phase,rem.make_year,rem.gps_address,rem.installation_type,"ON",rem.manufacturere,"NO","YES","0"]
                                    rm_sheet.append(li)
                                    rmline += 1

                        #4.3 Old Meter Reading
                        omr_sheet = book.create_sheet(title="4.3 Old Meter Reading")
                        print("Old Meter Readings")
                        omr_hd = ["NO","District","SPN","Old Meter Number","Meter Phase(1Ø/3Ø)","Installation Type(Faulty/Illegal Meter Replacement)","Meter Display ON/OFF"," Record Final KWh Reading from Meter Display"]
                        omr_sheet.append(omr_hd)
                        omrline = 1
                        for loc in Location.objects.all():

                            removed = RetiredMetersTransactions.objects.filter(date_removed__gte=start_date,date_removed__lte=end_date,box__location=loc)
                            if removed.count() > 0:
                                for rem in removed:
                                    print('installation type',rem.installation_type)
                                    li = [omrline,loc.loc_name,rem.spn,rem.old_meter_no,rem.phase,rem.installation_type,"ON",rem.final_readings]
                                    omr_sheet.append(li)
                                    omrline += 1

                        # districts data
                        print("Districk Pointers")
                        for loc in Location.objects.all():
                            name = loc.loc_name
                            code = loc.loc_id
                            this_sheet = book.create_sheet(title=f"{code} - {name}")
                            hd = ["No","District","FOC Company Name","SPN","Date of Installation","Meter Type","GPS or Digital Address","Installation Type","Serial Number for Meter to be replaced","Is Meter serial number same as work order?","Cable Re-Routing Required","Input Meter STS number","Meter Enclosure used?","Colours of Meter Seal Installed","CIU Handed over to Consumer"]
                            this_sheet.append(hd)
                            mx = 1
                            for service in ServiceOrder.objects.filter(ecg_date__gte=start_date,ecg_date__lte=end_date,location=loc,flag_for_invoice=True):
                                if len(service.old_meter_no) > 0:
                                    is_x = service.installation_type.name if service.installation_type else 'Unknown'
                                    print("ISX:",is_x)
                                    if True:
                                        rr = "YES" if service.is_routing else "NO"
                                        is_same = service.sn_same_as_wo().get('is_same')
                                        li = [mx,name,service.contractor.company,service.spn,service.ecg_date,service.meter_phase(),service.gps_code,is_x,service.spn,is_same,rr,service.new_meter,"YES","BLUE","YES"]
                                        mx += 1
                                        this_sheet.append(li)
                                else:
                                    li = [mx,name,service.contractor.company,service.spn,service.ecg_date,service.meter_phase(),service.gps_code,is_x,service.spn,"NO",rr,service.new_meter,"YES","BLUE","YES"]
                                    mx += 1
                                    this_sheet.append(li)

                    else:
                        sheet = book.active
                        sheet.title = "Meters Installed"
                        sn = 1
                        sheet.append(["SN","DATE INSTALLED","SERVICE","INSTALLATION TYPE","METER","SPN","OLD METER","PHASE","FOC","BOX","ROUTING","IS BOXED"])
                        for service in ServiceOrder.objects.filter(ecg_date__gte=start_date,ecg_date__lte=end_date,flag_for_invoice=True):
                            li = [sn,service.ecg_date,service.service_type.name,
                                  service.installation_type.name if service.installation_type else 'Unknown'
                                ,service.new_meter,service.spn,service.old_meter_no,service.meter_phase(),service.contractor.company,service.box_no,service.is_routing]
                            sheet.append(li)
                            sn += 1

                    import uuid
                    unique_id = uuid.uuid4()
                    filename = f"static/general/tmp/{for_invoice}_{unique_id}_{start_date}_to_{end_date}.xlsx"
                    book.save(filename)

                    success_response['message'] = filename
                    response = success_response

                elif module == 'not_returned_installations':
                    import openpyxl
                    book = openpyxl.Workbook()

                    total_sent = ServiceOrder.objects.filter(service_type__name__in=['Replacement', 'Regularization'],is_boxed=True).count()
                    total_not_sent = ServiceOrder.objects.filter(service_type__name__in=['Replacement', 'Regularization'],is_boxed=False).count()
                    total_expected = ServiceOrder.objects.filter(service_type__name__in=['Replacement', 'Regularization']).count()
                    xr = book.active
                    xr.append(["LEGEND","#"])
                    xr.append(["EXPECTED",total_expected])

                    xr.append(["SENT", total_sent])
                    xr.append(["REMAINING", total_not_sent])

                    foc_sheet  = book.create_sheet(title = "FOC")
                    foc_sheet.append(["FOC","TOTAL"])
                    for foc in Contractor.objects.all().order_by('company'):
                        total = ServiceOrder.objects.filter(contractor=foc,service_type__name__in=['Replacement', 'Regularization'],is_boxed=False).count()
                        foc_sheet.append([foc.company,total])

                    sheet = book.create_sheet(title = "RETIRED METERS")
                    sheet.title = "RETIRED METERS"
                    sheet.append(["LN","SERVICE","DATE","FOC","NEW METER","SPN","OLD METER"])
                    sn = 1
                    for service in ServiceOrder.objects.filter(service_type__name__in=['Replacement', 'Regularization'],is_boxed=False).order_by('ecg_date'):
                        li = [sn,service.service_type.name,service.ecg_date,service.contractor.company,service.new_meter,service.spn,service.old_meter_no]
                        sheet.append(li)
                        print(li)
                        sn += 1

                    import uuid
                    unique_id = uuid.uuid4()
                    filename = f"static/general/tmp/pending_retired_materials_{unique_id}.xlsx"
                    book.save(filename)

                    success_response['message'] = filename
                    response = success_response

                elif module == 'installation_type':
                    id = data.get('id', '*')
                    if id == '*':
                        installation_types = InstallationType.objects.all().order_by('name')
                        success_response['message'] = [installation_type.obj() for installation_type in
                                                       installation_types]
                    else:
                        installation_type = InstallationType.objects.get(id=id)
                        success_response['message'] = installation_type.obj()

                elif module == 'petty_cash':
                    entry_no = data.get('entry_no','*')
                    if entry_no == '*':
                        success_response['message'] = [pt.obj() for pt in PettyCash.objects.all()]
                    else:
                        success_response['message'] = [pt.obj() for pt in PettyCash.objects.filter(entry_no=entry_no)]

                elif module == 'order_type':
                    id = data.get('id', '*')
                    if id == '*':
                        order_types = ServiceOrderType.objects.all().order_by('name')
                        success_response['message'] = [order_type.obj() for order_type in
                                                       order_types]
                    else:
                        order_type = ServiceOrderType.objects.get(id=id)
                        success_response['message'] = order_type.obj()

                elif module == 'contractor_documents':
                    contactor_id = data.get('pk')
                    success_response['message'] = Contractor.objects.get(pk=contactor_id).documents()

                elif module == 'foc_otp':
                    phone = data.get('phone')
                    if Contractor.objects.filter(phone=phone).exists():
                        # generate opt
                        import random
                        otp = random.randint(101010, 999999)

                        contractor = Contractor.objects.get(phone=phone)
                        contractor.otp = otp
                        ct_email = contractor.email
                        contractor.save()

                        # Send OTP via SMS
                        to = phone.replace('233', '0').replace('+233', '0')
                        messta = f"Your OTP code is: {otp}"
                        if len(to) == 10:
                            sms_message = messta
                            Sms(
                                api=SmsApi.objects.get(sender_id='SNEDA SML') if SmsApi.objects.filter(sender_id='SNEDA SML').exists() else SmsApi.objects.get(is_default=True),
                                to=to,
                                message=sms_message
                            ).save()

                            MailQueues.objects.create(
                                sender=MailSenders.objects.get(is_default=True),
                                body=messta,
                                recipient=ct_email,
                                mail_key=make_md5_hash(f"{messta}{to}{ct_email}"),
                                subject="Sneda SML OTP Verification"
                            )

                        success_response['message'] = otp
                    else:
                        raise Exception("Contractor does not exist")

                elif module == 'foc_verify_token':
                    foc_verify_token = data.get('code')
                    print(data)
                    print(foc_verify_token)
                    if Contractor.objects.filter(otp=foc_verify_token).exists():
                        contractor = Contractor.objects.get(otp=foc_verify_token)
                        c_code = contractor.code
                        code = c_code
                        contractor.otp = None
                        contractor.save()
                        success_response['message'] = Contractor.objects.get(code=code).minimal_obj()
                    else:
                        raise Exception("Invalid OTP")

                elif module == 'foc_portal':
                    foc_id = data.get('foc_id')
                    print(foc_id)
                    contractor = Contractor.objects.get(code=foc_id)

                    arr = contractor.obj()
                    print(arr)

                    success_response['message'] = arr

                elif module == 'transfer':
                    id = data.get('id','*')
                    if id == '*':
                        transfers = TransferHd.objects.all().order_by('entry_date')
                        success_response['message'] = [transfer.obj() for transfer in transfers]
                    else:
                        if isinstance(id, int) or (isinstance(id, str) and id.isdigit()):
                            transfer = TransferHd.objects.filter(id=id)
                        else:
                            transfer = TransferHd.objects.filter(entry_no=id)

                        success_response['message'] = [t.obj() for t in transfer]


                elif module == 'job_material_details':
                    contractor_code = data.get('code','*')
                    contractor = Contractor.objects.get(code=contractor_code)

                    import openpyxl
                    book = openpyxl.Workbook()
                    sheet = book.active

                    for job in ServiceOrder.objects.filter(contractor=contractor):
                        jb = job.obj()
                        meter = job.new_meter
                        customer = job.customer
                        customer_no = job.customer_no
                        sheet.append(['#############################'])
                        sheet.append(["METER","CUSTOMER"])
                        sheet.append([meter,f"[{customer} - {customer_no}]"])

                        sheet.append(['MATERIAL',"QUANTITY"])
                        mats = MaterialOrderItem.objects.filter(service_order=job,material_type='is')
                        print(mats)
                        for material in mats:

                            sheet.append([material.material.name,material.quantity])
                        sheet.append(['#############################'])
                        sheet.append([''])

                    file_name = f'static/general/tmp/{contractor.company}.xlsx'
                    book.save(file_name)



                    success_response['message'] = file_name

                    response = success_response

                elif module == 'month_walk':

                    from datetime import datetime
                    location = '*'
                    if data.get('location'):
                        location = Location.objects.get(id=data.get('location'))
                    now = datetime.now()
                    year = now.year
                    current_month = now.month
                    months = [["Month","Stock","Installed"]]
                    import openpyxl
                    wb = openpyxl.Workbook()
                    ws = wb.active
                    header = ['MONTH',"STOCK",'INSTALLED','%']
                    ws.append(header)

                    for month in range(1, current_month + 1):
                        import calendar
                        month_name = calendar.month_name[month]
                        # Get stock of sum of material in cardex, within this month
                        from django.db.models import Sum
                        # Calculate the first and last day of the month
                        from datetime import datetime
                        first_day = datetime(year, month, 1)
                        if month == 12:
                            last_day = datetime(year + 1, 1, 1)
                        else:
                            last_day = datetime(year, month + 1, 1)
                        # Aggregate sum of material quantity in cardex for this month

                        if location == '*':
                            stock_sum = Cardex.objects.filter(
                                created_at__lte=last_day,
                                material__item_type='pri'
                                ).aggregate(total=Sum('qty'))['total'] or 0
                        else:
                            stock_sum = Cardex.objects.filter(

                                created_at__lte=last_day,
                                material__item_type='pri',
                                location=location
                                ).aggregate(total=Sum('qty'))['total'] or 0

                        from decimal import Decimal
                        stock_sum = int(stock_sum)
                        print(stock_sum, type(stock_sum))

                        from ssml.models import ServiceOrder
                        if location == '*':
                            total_service_orders = ServiceOrder.objects.filter(ecg_date__gte=first_day, ecg_date__lt=last_day).count()
                        else:
                            total_service_orders = ServiceOrder.objects.filter(ecg_date__gte=first_day, ecg_date__lt=last_day,location=location).count()


                        stock_sum = round(stock_sum, 2)
                        months.append([month_name,stock_sum,total_service_orders])
                        # INSERT_YOUR_CODE
                        percent = 0
                        if stock_sum > 0:
                            percent = round((total_service_orders / stock_sum) * 100, 2)
                        else:
                            percent = 0
                        ws.append([month_name,stock_sum,total_service_orders,percent])

                    file = fr"static/general/tmp/status.xlsx"
                    wb.save(file)
                    success_response['message'] = months
                    success_response['file'] = file
                    response = success_response

                elif module == 'location':
                    id = data.get('id','*')
                    doc = data.get('doc', 'json')
                    if doc == 'excel':
                        import openpyxl
                        book = openpyxl.Workbook()
                        sheet = book.active
                        sheet.title = "Locations"
                        sheet.append(["LOC ID", "NAME", "COUNTRY", "CITY", "STREET", "ADDRESS", "PHONE", "EMAIL", "DEFAULT"])
                        for loc in Location.objects.all().order_by('loc_name'):
                            sheet.append([
                                loc.loc_id,
                                loc.loc_name,
                                loc.country,
                                loc.city,
                                loc.street,
                                loc.address,
                                loc.phone,
                                loc.email,
                                "YES" if loc.is_default else "NO"
                            ])
                        import uuid
                        unique_id = uuid.uuid4()
                        filename = f"static/general/tmp/locations_{unique_id}.xlsx"
                        book.save(filename)
                        success_response['message'] = filename
                    else:
                        if id == '*':
                            success_response['message'] = [loc.obj() for loc in Location.objects.all().order_by('loc_name')]
                        else:
                            success_response['message'] = [loc.obj() for loc in Location.objects.filter(id=id)]


                elif module == 'expense':
                    from django.db.models import Sum
                    from datetime import datetime
                    id = data.get('id','*')
                    limit = data.get('limit',10000)
                    as_of = data.get('as_of', f'{datetime.now().year}-01-01')
                    doc = data.get('doc','json')
                    direction = data.get('direction')
                    print(data)
                    arr = []
                    if id == '*':
                        filt = data.get('filter','pending')
                        print(filt)
                        if filt == 'approved':
                            expenses = Expense.objects.filter(is_approved=True).order_by('date')
                        elif filt == 'pending':
                            expenses = Expense.objects.filter(is_approved=False,is_rejected=False).order_by('date')
                        elif filt == 'rejected':
                            expenses = Expense.objects.filter(is_rejected=True).order_by('date')
                        else:
                            expenses = Expense.objects.flter(is_rejected=False,is_approved=True).order_by('date')

                        if doc == 'json':
                            arr  = [expense.obj() for expense in expenses]

                        if doc == 'excel':
                            import openpyxl
                            wb = openpyxl.Workbook()
                            ws = wb.active
                            header = [
                                "ID","DIRECTION","CATEGORY","TYPE","DATE","REFERENCE","DESCRIPTION","AMOUNT","EVIDENCE"
                            ]
                            ws.append(header)


                            for expense in expenses:
                                transaction = expense
                                tr = [expense.pk,expense.direction,expense.category,expense.amount,expense.date,expense.reference,expense.description]
                                evidence = expense.evidence()
                                x_file = ""
                                if len(evidence) > 0:
                                    lx = evidence.split(',')

                                    for lu in lx:
                                        file = lu.split('|')[-1].lstrip('/')
                                        file_url = f"{BASE_URL}{file}"
                                        short_link = shorten_url(file_url)
                                        x_file += f"{short_link},"

                                    x_file = x_file.rstrip(',')
                                    print(x_file)

                                li = [transaction.direction,transaction.category,transaction.transaction_type,transaction.date,transaction.reference,transaction.description,transaction.amount,x_file]
                                ws.append(li)

                            dir_name = direction if direction != '*' else 'all'
                            import uuid
                            unique_id = uuid.uuid4()
                            file_name = f'static/general/tmp/{unique_id}_d{dir_name}_expensis_as_of_{str(as_of)}.xlsx'
                            wb.save(file_name)
                            arr = file_name

                    else:
                        expense = Expense.objects.get(id=id)
                        arr = expense.obj()

                    if filt == 'approved':
                        success_response['message'] = {
                            'total': "{:,.2f}".format(Expense.objects.filter(is_approved=True,is_rejected=False).aggregate(total=Sum('amount'))['total'] or 0),
                            'total_in': "{:,.2f}".format(Expense.objects.filter(direction='in',is_approved=True).aggregate(total=Sum('amount'))['total'] or 0),
                            'total_out': "{:,.2f}".format(Expense.objects.filter(direction='out',is_approved=True).aggregate(total=Sum('amount'))['total'] or 0),
                            'expenses':arr
                        }
                    else:
                        success_response['message'] = {
                            'total': "{:,.2f}".format(Expense.objects.filter(is_approved=False).aggregate(total=Sum('amount'))['total'] or 0),
                            'total_in': "{:,.2f}".format(Expense.objects.filter(direction='in',is_approved=False).aggregate(total=Sum('amount'))['total'] or 0),
                            'total_out': "{:,.2f}".format(Expense.objects.filter(direction='out',is_approved=False).aggregate(total=Sum('amount'))['total'] or 0),
                            'expenses':arr
                        }

                elif module == 'find_expense_by_search':
                    from django.db.models import Q

                    search_string = data.get('search_string')

                    # Using Q objects to search both fields with 'icontains' (Case-Insensitive LIKE)
                    expenses = Expense.objects.filter(
                        Q(description__icontains=search_string) |
                        Q(reference__icontains=search_string)
                    ).order_by('date')

                    arr = [expense.obj() for expense in expenses]
                    success_response['message'] = arr
                    response = success_response

                elif module == 'foc_invoice':

                    entry_no = data.get('entry_no','*')
                    if entry_no == '*':
                        arr = [inv.obj() for inv in FocInvoiceHd.objects.all()]
                    else:
                        arr = [inv.obj() for inv in FocInvoiceHd.objects.filter(entry_no=entry_no)]

                    success_response['message'] = arr

                elif module == 'ecg_eligible_jobs':
                    location_id = data.get('location', '*')
                    eligible_jobs = ServiceOrder.objects.filter(status='completed', is_ecg_invoiced=False)
                    if location_id != '*':
                        eligible_jobs = eligible_jobs.filter(location_id=location_id)

                    res = []
                    for job in eligible_jobs:
                        # Get job rate if exists
                        rate_obj = ECGJobRate.objects.filter(service_type=job.service_type).first()
                        rate = float(rate_obj.rate) if rate_obj else float(job.total_amount) if job.total_amount else 0.0

                        res.append({
                            'id': job.id,
                            'date': str(job.ecg_date),
                            'service': job.service_type.name,
                            'meter': job.new_meter,
                            'contractor': job.contractor.company,
                            'amount': rate
                        })
                    success_response['message'] = res

                elif module == 'ecg_rates':
                    job_rates = [r.obj() for r in ECGJobRate.objects.all()]
                    meter_rates = [r.obj() for r in ECGMeterRate.objects.all()]
                    success_response['message'] = {
                        'job_rates': job_rates,
                        'meter_rates': meter_rates
                    }

                elif module == 'billable_materials':
                    materials = [m.obj() for m in InventoryMaterial.objects.filter(is_billable=True, is_active=True)]
                    success_response['message'] = materials

                elif module == 'ecg_invoice':
                    id = data.get('id', '*')
                    if id == '*':
                         success_response['message'] = [inv.obj() for inv in EcgInvoiceHd.objects.all().order_by('-entry_date')]
                    else:
                         invoice = EcgInvoiceHd.objects.get(id=id)
                         res = invoice.obj()
                         prev_inv = EcgInvoiceHd.objects.filter(id__lt=id).order_by('-id').first()
                         next_inv = EcgInvoiceHd.objects.filter(id__gt=id).order_by('id').first()
                         res['previous'] = prev_inv.id if prev_inv else None
                         res['next'] = next_inv.id if next_inv else None

                         # Supplied Meters Tab
                         supplied_meters = [item.obj() for item in EcgInvoiceHd.objects.filter(entry=invoice)]
                         res['supplied_meters'] = supplied_meters

                         # Jobs Done Tab
                         jobs_done = []
                         for t in ECGInvoiceTransactions.objects.filter(entry=invoice):
                             jobs_done.append({
                                 'id': t.id,
                                 'service_order': {
                                     'service_date': str(t.service_order.ecg_date),
                                     'service_type': {'name': t.service_order.service_type.name},
                                     'new_meter_no': t.service_order.new_meter,
                                     'contractor': {'name': t.service_order.contractor.company}
                                 },
                                 'amount': float(t.amount)
                             })
                         res['jobs_done'] = jobs_done

                         # Meters Invoiced For Tab (Combined/Aggregated)
                         # Simply return the same as supplied_meters or a filtered list
                         res['meters_invoiced_for'] = supplied_meters

                         success_response['message'] = res

                elif module == 'print_invoice':
                    id = data.get('id')
                    invoice = InvoiceHD.objects.get(id=id)

                    from fpdf import FPDF
                    pdf = FPDF()
                    pdf.add_page()

                    pdf.set_font("Arial","",10)
                    pdf.cell(190, 5, txt="Sneda Smart Meters Limited", ln=True, border=0, align="C")
                    pdf.cell(190, 5, txt="P.O. Box 1024, Accra, Ghana", ln=True, border=0, align="C")
                    pdf.cell(190, 5, txt="Tel: +233 54 631 0011", ln=True, border=0, align="C")
                    pdf.cell(190, 5, txt="Email: solomon@snedaghana.com", ln=True, border=0, align="C")
                    pdf.ln(10)

                    pdf.set_font("Arial","B", size=20)
                    pdf.cell(190, 5, txt="JOBS COMPLETED DOCUMENT", ln=True, border=0, align="C")
                    pdf.ln(10)

                    pdf.set_font("Arial","B", size=12)
                    pdf.cell(95, 5, txt=invoice.contractor.company, ln=False, align="L",border=0)


                    pdf.set_font("Arial", "B", size=12)
                    pdf.cell(95, 5, txt=str(f"GHS {invoice.total_amount:,.2f}"), ln=True, align="R",border=0)

                    pdf.set_font("Arial","B", size=10)
                    pdf.cell(50, 5, txt="SERVICE", ln=False, align="L",border=1)
                    pdf.cell(50, 5, txt="Date.", ln=False, align="L",border=1)
                    pdf.cell(50, 5, txt="Asset", ln=False, align="L",border=1)
                    pdf.cell(40, 5, txt="Amount", ln=True, align="L",border=1)

                    pdf.set_font("Arial","", size=8)
                    for transaction in InvoiceTransactions.objects.filter(entry=invoice):
                        pdf.cell(50, 5, txt=transaction.remarks, ln=False, align="L",border=1)
                        pdf.cell(50, 5, txt=str(transaction.service_date), ln=False, align="L",border=1)
                        pdf.cell(50, 5, txt=transaction.asset, ln=False, align="L",border=1)
                        pdf.cell(40, 5, txt=str(transaction.amount), ln=True, align="L",border=1)

                    pdf.multi_cell(190, 10, txt="This document is subject to review and is not a payslip. After review, an official invoice will be sent to you to commerce payment",border=False, align="L")


                    pdf.ln(5)
                    pdf.set_font("Arial", size=8)
                    pdf.cell(190 / 6, 8, txt=f"{invoice.created_by.first_name} {invoice.created_by.last_name}", ln=False, align="C",border=1)
                    pdf.cell(190 / 6, 8, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 12, 8, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 6, 8, txt=f"{invoice.approved_by.get_full_name() if invoice.approved_by else ''}", ln=False, align="C",border=1)
                    pdf.cell(190 / 12, 8, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 6, 8, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 6, 8, txt="", ln=True, align="R",border=1)


                    pdf.cell(190 / 6, 8, txt="Created By", ln=False, align="C",border=0)
                    pdf.cell(190 / 6, 8, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 12, 8, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 6, 8, txt="Posted By", ln=False, align="C",border=0)
                    pdf.cell(190 / 12, 8, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 6, 8, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 6, 8, txt="Confirmed By", ln=True, align="C",border=0)



                    file_name = f'static/general/tmp/{invoice.entry_no}.pdf'
                    pdf.output(file_name)

                    success_response['message'] = f"/{file_name}"


                elif module == 'print_tr':
                    entry_no = data.get('entry_no')

                    entry = TransferHd.objects.get(entry_no=entry_no)

                    from fpdf import FPDF
                    pdf = FPDF()
                    pdf.add_page()

                # INSERT_YOUR_CODE
                    pdf = FPDF(orientation='L', unit='mm', format='A4')
                    pdf.add_page()
                    pdf.set_auto_page_break(auto=True, margin=15)

                    # Define a function to draw the header on each page
                    def draw_waybill_header(pdf):
                        # Logo
                        safe_add_image_to_pdf(pdf, 'static/general/logo.png', x=10, y=8, w=35)

                        # Title
                        pdf.set_font("Arial", 'B', 20)
                        pdf.set_xy(70, 10)
                        pdf.cell(0, 10, "SNEDA SMART METERS", ln=1, align="L")

                        # WAYBILL
                        pdf.set_font("Arial", 'B', 18)
                        pdf.set_xy(230, 10)
                        pdf.cell(0, 10, f"WAYBILL: {entry.entry_no}", ln=1, align="L")

                        # TO, ADDRESS, STATION
                        pdf.set_font("Arial", '', 12)
                        pdf.set_xy(70, 20)
                        pdf.cell(0, 8, f"FROM:  {entry.loc_fr.loc_name}", ln=1, align="L")
                        pdf.set_xy(70, 28)
                        pdf.cell(0, 8, f"TO:  {entry.loc_to.loc_name}   DISPATCH:  {entry.car_no}", ln=1, align="L")

                        # Table header
                        pdf.set_xy(10, 40)
                        pdf.set_font("Arial", 'B', 11)
                        col_widths = [15, 35, 137, 30, 30, 30]
                        headers = ["SN", "ITEM CODE", "DESCRIPTION","UOM", "SENT", "RECIEVED"]
                        for i, header in enumerate(headers):
                            pdf.cell(col_widths[i], 10, header, border=1, align="C")
                        pdf.ln()
                        return col_widths

                    # Custom class to override header
                    from fpdf import FPDF as _FPDF
                    class WaybillPDF(_FPDF):
                        def header(self):
                            # Save current y to restore after header
                            y = self.get_y()
                            draw_waybill_header(self)
                            # Set y to just below the table header
                            self.set_y(50)
                        def footer(self):
                            # Move 40mm from bottom

                            self.set_y(-40)
                            self.set_font("Arial", 'i', 8)
                            page_width = self.w - self.l_margin - self.r_margin
                            col_footer_width = page_width / 3
                            # Draw signature lines
                            self.cell(page_width,8,"Acraa, Osu, +233 24 350 0687, bharat@snedaghana.com",ln=1,align='C')
                            self.set_font("Arial", 'B', 11)
                            self.cell(col_footer_width, 8, "Sender", border="LTR", align="C")
                            self.cell(col_footer_width, 8, "Delivered By", border="LTR", align="C")
                            self.cell(col_footer_width, 8, "Received By", border="LTR", align="C")
                            self.ln(8)

                            self.set_font("Arial", '', 11)
                            self.cell(col_footer_width, 8, f"{entry.obj().get('sent_by')}", border="LR", align="C")
                            self.cell(col_footer_width, 8, f"{entry.obj().get('transporter')}", border="LR", align="C")
                            self.cell(col_footer_width, 8, "", border="LR", align="C")
                            self.ln(1)

                            self.set_font("Arial", '', 11)
                            self.cell(col_footer_width, 12, "_________________________", border="LRB", align="C")
                            self.cell(col_footer_width, 12, "_________________________", border="LRB", align="C")
                            self.cell(col_footer_width, 12, "_________________________", border="LRB", align="C")
                            self.ln(12)

                    pdf = WaybillPDF(orientation='L', unit='mm', format='A4')
                    pdf.set_auto_page_break(auto=True, margin=40)
                    pdf.add_page()
                    col_widths = [15, 35, 137, 30, 30, 30]  # For use in data rows

                    # Dummy data rows
                    pdf.set_font("Arial", '', 11)

                    dummy_data = [
                        # [1, "SM-1001", "Single Phase Smart Meter", 10, "10", ""],
                    ]

                    line = 1
                    for tran in entry.transactions():
                        recieved = tran.get('received_qty') if entry.is_posted else ""
                        dummy_data.append(
                            [line,tran.get('barcode'),tran.get('name'),tran.get('oum'),tran.get('total_qty'),recieved]
                        )
                        line += 1
                    for row in dummy_data:
                        for i, item in enumerate(row):
                            align = "C" if i in [0,3,4,5] else "L"
                            pdf.cell(col_widths[i], 10, str(item), border=1, align=align)
                        pdf.ln()

                    # Fill up to 12 rows for visual
                    for _ in range(12 - len(dummy_data)):
                        for w in col_widths:
                            pdf.cell(w, 10, "", border=1)
                        pdf.ln()

                    # Footer lines


                    # Footer fields
                    # Footer with three columns: Sender, Delivered By, Received By, on every page
                    class WaybillPDF(_FPDF):
                        def header(self):
                            y = self.get_y()
                            draw_waybill_header(self)
                            self.set_y(50)



                    file_name = f"{entry_no}.pdf"
                    file = f"static/general/tmp/{file_name}"
                    pdf.output(file)

                    success_response['message'] = file


                elif module == 'cont_issued':
                    cont_pk = data.get('contractor','*')
                    if cont_pk == '*':
                        issueds = Issue.objects.all().order_by('issue_date')
                    else:
                        issueds = Issue.objects.filter(contractor_id=cont_pk).order_by('issue_date')



                    if data.get('type') == 'ISS':
                        issueds = issueds.filter(issue_type='ISS')
                    elif data.get('type') == 'RET':
                        issueds = issueds.filter(issue_type='RET')

                    success_response['message'] = [
                        {"pk":issue.id,'entry':issue.issue_no,'remarks':issue.remarks,'date':issue.issue_date,'is_posted':issue.is_posted,'deleted':issue.is_deleted,'total_qty':issue.total_qty()}
                     for issue in issueds]

                elif module == 'export_installations':
                    service_type = data.get('service_type','*')
                    print(data)
                    if service_type == '*':
                        installations = ServiceOrder.objects.all()
                    else:
                        st = ServiceType.objects.get(id=service_type)
                        installations = ServiceOrder.objects.filter(service_type=st)

                    doc = data.get('doc','JSON')
                    if doc == 'JSON':
                        success_response['message'] = [installation.obj() for installation in installations]
                    elif doc == 'EXCEL':
                        import openpyxl
                        book = openpyxl.Workbook()
                        sheet = book.active
                        sheet.title = "Installations"
                        sheet.append(['Service Type', 'Service Date', 'Contractor', 'Plot', 'Geo Code', 'Customer', 'Customer No', 'Old Meter No', 'New Meter No', 'Old Meter No Reading', 'New Meter No Reading'])
                        for installation in installations:
                            sheet.append([installation.service_type.name, installation.service_date, installation.contractor.company, installation.plot.plot_no, installation.geo_code, installation.customer, installation.customer_no, installation.old_meter_no, installation.new_meter, installation.old_meter_no_reading, installation.new_meter_no_reading])
                        file_name = f"static/general/tmp/Installations-{st.name}.xlsx"
                        book.save(file_name)
                        success_response['message'] = f'{file_name}'

                elif module == 'cardex':
                    pk = data.get('pk')
                    item = InventoryMaterial.objects.get(id=pk)
                    loc_id = data.get('location','*')
                    if loc_id == '*':
                        file_name = 'all_locations'
                    else:
                        file_name = Location.objects.get(id=loc_id).loc_name

                    cd = item.cardex(loc_id)

                    # make excel
                    import openpyxl
                    book = openpyxl.Workbook()
                    sheet = book.active
                    sheet.title = "Cardex"
                    sheet.append(['Location','Doc No', 'Doc Type', 'Qty',"Balance", 'Created At'])
                    for row in cd:
                        sheet.append([row.get('location'),row.get('doc_no'),row.get('doc_type'),row.get('qty'),row.get('balance'),row.get('created_at')])

                    import hashlib
                    name = hashlib.md5(item.name.encode()).hexdigest()
                    file_name = f"static/general/tmp/{file_name}-Cardex-{name}.xlsx"
                    book.save(file_name)


                    arr = {
                        'json':cd,
                        'excel':file_name
                    }
                    success_response['message'] = arr
                    response = success_response

                elif module == 'group':
                    id = data.get('id','*')
                    if id == '*':
                        groups = InventoryGroup.objects.all()
                        success_response['message'] = [group.obj() for group in groups]
                    else:
                        group = InventoryGroup.objects.get(id=id)
                        success_response['message'] = group.obj()
                elif module == 'material':
                    id = data.get('id','*')
                    if id == '*':
                        materials = InventoryMaterial.objects.all().order_by('name')
                        success_response['message'] = [material.obj() for material in materials]
                    else:
                        if str(id).isdigit():
                            material = InventoryMaterial.objects.get(id=id)
                            success_response['message'] = material.obj()
                        else:
                            material = InventoryMaterial.objects.filter(Q(barcode__icontains=id) | Q(name__icontains=id))
                            filta = data.get('filter', None)
                            if filta is not None:
                                    if filta == 'is_return':
                                        material = material.filter(is_return=True)
                            if material.exists():

                                success_response['message'] = [m.obj() for m in material]
                            else:
                                success_response['status_code'] = 404
                                success_response['message'] = f"No material with barcode or name matching {id} with filter {filta}"


                elif module == 'meter':
                    meter_no=data.get('meter_no')
                    meter = Meter.objects.get(meter_no=meter_no)
                    arr = meter.obj()
                    print(meter.obj())

                    success_response['message'] = arr

                elif module == 'supplier':
                    id = data.get('id','*')
                    if id == '*':
                        suppliers = Supplier.objects.all()
                        success_response['message'] = [supplier.obj() for supplier in suppliers]
                    else:
                        supplier = Supplier.objects.get(id=id)
                        success_response['message'] = supplier.obj()

                elif module == 'grn':
                    id = data.get('id','*')
                    if id == '*':
                        grns = Grn.objects.all()
                        success_response['message'] = [grn.obj() for grn in grns]
                    else:
                        if id.isdigit():
                            grn = Grn.objects.get(id=id)
                        else:
                            grn = Grn.objects.get(grn_no=id)
                        success_response['message'] = grn.obj()

                elif module == 'plot':
                    id = data.get('id','*')
                    if id == '*':
                        plots = Plot.objects.all()
                        success_response['message'] = [plot.obj() for plot in plots]
                    else:
                        plot = Plot.objects.get(id=id)
                        success_response['message'] = plot.obj()

                elif module == 'service_type':
                    id = data.get('id','*')
                    if id == '*':
                        service_types = ServiceType.objects.all()
                        success_response['message'] = [service_type.obj() for service_type in service_types]
                    else:
                        service_type = ServiceType.objects.get(id=id)
                        success_response['message'] = service_type.obj()

                elif module == 'service':
                    id = data.get('id','*')
                    if id == '*':
                        services = Service.objects.all()
                        success_response['message'] = [service.obj() for service in services]
                    else:
                        service = Service.objects.get(id=id)
                        success_response['message'] = service.obj()
                elif module == 'print_grn':
                    grn = Grn.objects.get(id=data.get('id'))

                    from fpdf import FPDF

                    class ModernPDF(FPDF):
                        def footer(self):
                            self.set_y(-15)
                            self.set_font("Helvetica", "I", 8)
                            self.set_text_color(150, 150, 150)
                            self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", 0, 0, "C")

                    def clean_str(s):
                        if not s:
                            return ""
                        s = str(s)
                        for orig, repl in {
                            '\u2018': "'",
                            '\u2019': "'",
                            '\u201C': '"',
                            '\u201D': '"',
                            '\u2014': '-',
                        }.items():
                            s = s.replace(orig, repl)
                        return s.encode('latin-1', 'ignore').decode('latin-1')

                    import os
                    logo_path = None
                    for path in [
                        f"{COMPANY_DETAILS.get('COMPANY_LOGO')}",
                        'static/general/logo.png',
                        'static/assets/img/logo.png',
                        'static/general/ssml.png',
                    ]:
                        if os.path.exists(path):
                            logo_path = path
                            break

                    pdf = ModernPDF()
                    pdf.alias_nb_pages()
                    pdf.set_margins(15, 15, 15)
                    pdf.add_page()

                    # Header Section with Company details
                    start_y = 15
                    if logo_path:
                        pdf.image(logo_path, x=15, y=start_y, h=15)
                        pdf.set_y(start_y)
                        pdf.set_x(105)
                        pdf.set_font("Helvetica", "B", 10)
                        pdf.set_text_color(44, 62, 80)
                        pdf.cell(90, 4, txt=f"{COMPANY_DETAILS.get('name')}", ln=True, align="R")

                        pdf.set_x(105)
                        pdf.set_font("Helvetica", "", 8)
                        pdf.set_text_color(100, 100, 100)
                        pdf.cell(90, 3.5, txt=f"{COMPANY_DETAILS.get('postal_address')}", ln=True, align="R")

                        pdf.set_x(105)
                        pdf.cell(90, 3.5, txt=f"Tel: {COMPANY_DETAILS.get('phone')}", ln=True, align="R")

                        pdf.set_x(105)
                        pdf.cell(90, 3.5, txt=f"Email: {COMPANY_DETAILS.get('email')}", ln=True, align="R")
                    else:
                        pdf.set_y(start_y)
                        pdf.set_font("Helvetica", "B", 11)
                        pdf.set_text_color(44, 62, 80)
                        pdf.cell(180, 4.5, txt=f"{COMPANY_DETAILS.get('name')}", ln=True, align="L")

                        pdf.set_font("Helvetica", "", 8.5)
                        pdf.set_text_color(100, 100, 100)
                        pdf.cell(180, 4, txt=f"{COMPANY_DETAILS.get('postal_address')}", ln=True, align="L")
                        pdf.cell(180, 4, txt=f"Tel: {COMPANY_DETAILS.get('phone')}", ln=True, align="L")
                        pdf.cell(180, 4, txt=f"Email: {COMPANY_DETAILS.get('email')}", ln=True, align="L")

                    pdf.set_y(34)
                    pdf.set_font("Helvetica", "B", 14)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(180, 6, txt="GOODS RECEIVED NOTE", ln=True, border=0, align="L")

                    pdf.set_draw_color(44, 62, 80)
                    pdf.set_line_width(0.6)
                    current_y = pdf.get_y()
                    pdf.line(15, current_y + 1, 195, current_y + 1)

                    # Gap before metadata layout
                    pdf.set_y(current_y + 5)

                    # Metadata Fields Sanitization
                    grn_no = clean_str(grn.grn_no)
                    supplier_id = clean_str(grn.supplier.id if grn.supplier else "")
                    grn_date = clean_str(grn.grn_date)
                    supplier_name = clean_str(grn.supplier.supplier_name if grn.supplier else "")
                    remarks = clean_str(grn.remarks)
                    supplier_phone = clean_str(grn.supplier.supplier_phone if (grn.supplier and grn.supplier.supplier_phone) else "")

                    # Metadata Layout (2 Columns)
                    # Row 1
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(120, 120, 120)
                    pdf.cell(25, 6, "ENTRY NO:", ln=False)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(51, 51, 51)
                    pdf.cell(65, 6, grn_no, ln=False)

                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(120, 120, 120)
                    pdf.cell(30, 6, "SUPPLIER CODE:", ln=False)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(51, 51, 51)
                    pdf.cell(60, 6, supplier_id, ln=True)

                    # Row 2
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(120, 120, 120)
                    pdf.cell(25, 6, "GRN DATE:", ln=False)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(51, 51, 51)
                    pdf.cell(65, 6, grn_date, ln=False)

                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(120, 120, 120)
                    pdf.cell(30, 6, "SUPPLIER NAME:", ln=False)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(51, 51, 51)
                    pdf.cell(60, 6, supplier_name, ln=True)

                    # Row 3
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(120, 120, 120)
                    pdf.cell(25, 6, "REMARKS:", ln=False)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(51, 51, 51)
                    pdf.cell(65, 6, remarks, ln=False)

                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(120, 120, 120)
                    pdf.cell(30, 6, "SUPPLIER PHONE:", ln=False)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(51, 51, 51)
                    pdf.cell(60, 6, supplier_phone, ln=True)

                    pdf.ln(8)

                    # Table Header Styling
                    pdf.set_draw_color(220, 224, 230)
                    pdf.set_line_width(0.1)
                    pdf.set_fill_color(240, 244, 248)
                    pdf.set_text_color(44, 62, 80)
                    pdf.set_font("Helvetica", "B", 8)

                    # Columns widths: 8, 22, 50, 15, 17, 17, 17, 17, 18 -> Total: 180
                    pdf.cell(8, 8, txt="LN", ln=False, border=1, align="L", fill=True)
                    pdf.cell(22, 8, txt="Barcode", ln=False, border=1, align="L", fill=True)
                    pdf.cell(50, 8, txt="Name", ln=False, border=1, align="L", fill=True)
                    pdf.cell(15, 8, txt="UOM", ln=False, border=1, align="C", fill=True)
                    pdf.cell(17, 8, txt="Pak. Qty", ln=False, border=1, align="R", fill=True)
                    pdf.cell(17, 8, txt="Qty", ln=False, border=1, align="R", fill=True)
                    pdf.cell(17, 8, txt="Tot. Qty", ln=False, border=1, align="R", fill=True)
                    pdf.cell(17, 8, txt="Rate", ln=False, border=1, align="R", fill=True)
                    pdf.cell(18, 8, txt="Tot. Amt", ln=True, border=1, align="R", fill=True)

                    line = 1
                    total_qty = 0
                    total_amount = 0

                    pdf.set_font("Helvetica", "", 8)
                    pdf.set_text_color(51, 51, 51)

                    for transaction in GrnTransaction.objects.filter(grn=grn):
                        t_name = clean_str(transaction.name)[:25]
                        t_barcode = clean_str(transaction.barcode)
                        t_uom = clean_str(transaction.uom)

                        pdf.cell(8, 7, txt=str(line), ln=False, border=1, align="L")
                        pdf.cell(22, 7, txt=t_barcode, ln=False, border=1, align="L")
                        pdf.cell(50, 7, txt=t_name, ln=False, border=1, align="L")
                        pdf.cell(15, 7, txt=t_uom, ln=False, border=1, align="C")
                        pdf.cell(17, 7, txt=str(transaction.pack_qty), ln=False, border=1, align="R")
                        pdf.cell(17, 7, txt=str(transaction.qty), ln=False, border=1, align="R")
                        pdf.cell(17, 7, txt=str(transaction.total_qty), ln=False, border=1, align="R")

                        try:
                            rate_val = f"{float(transaction.rate):,.2f}"
                        except (ValueError, TypeError):
                            rate_val = str(transaction.rate)

                        try:
                            amount_val = f"{float(transaction.amount):,.2f}"
                        except (ValueError, TypeError):
                            amount_val = str(transaction.amount)

                        pdf.cell(17, 7, txt=rate_val, ln=False, border=1, align="R")
                        pdf.cell(18, 7, txt=amount_val, ln=True, border=1, align="R")

                        line += 1
                        total_qty += transaction.total_qty if transaction.total_qty else 0
                        total_amount += transaction.amount if transaction.amount else 0

                    # Table Footer divider line
                    pdf.set_draw_color(180, 180, 180)
                    pdf.set_line_width(0.2)
                    pdf.cell(180, 2, txt="", ln=True, border="T")

                    # Totals
                    try:
                        tot_amt_str = f"{float(total_amount):,.2f}"
                    except (ValueError, TypeError):
                        tot_amt_str = str(total_amount)

                    try:
                        tot_qty_str = f"{int(total_qty):,}"
                    except (ValueError, TypeError):
                        tot_qty_str = str(total_qty)

                    pdf.set_font("Helvetica", "B", 9)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(145, 6, txt="Total Qty: ", ln=False, align="R", border=0)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(51, 51, 51)
                    pdf.cell(35, 6, txt=tot_qty_str, ln=True, align="R", border=0)

                    pdf.set_font("Helvetica", "B", 9)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(145, 6, txt="Total Amount: ", ln=False, align="R", border=0)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(51, 51, 51)
                    pdf.cell(35, 6, txt=tot_amt_str, ln=True, align="R", border=0)

                    # Signatures Section
                    pdf.ln(12)
                    pdf.set_draw_color(180, 180, 180)
                    pdf.set_line_width(0.2)

                    created_by_name = clean_str(f"{grn.created_by.first_name} {grn.created_by.last_name}")
                    posted_by_name = clean_str(grn.obj().get('posted_by'))
                    if posted_by_name == 'None' or not posted_by_name:
                        posted_by_name = ""

                    sig_h = 10
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(51, 51, 51)

                    # Draw signature lines
                    pdf.cell(45, sig_h, txt=created_by_name, ln=False, align="C", border="B")
                    pdf.cell(22.5, sig_h, txt="", ln=False, border=0)
                    pdf.cell(45, sig_h, txt=posted_by_name, ln=False, align="C", border="B")
                    pdf.cell(22.5, sig_h, txt="", ln=False, border=0)
                    pdf.cell(45, sig_h, txt="", ln=True, align="C", border="B")

                    # Draw signature labels
                    pdf.ln(2)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(120, 120, 120)

                    pdf.cell(45, 5, txt="CREATED BY", ln=False, align="C", border=0)
                    pdf.cell(22.5, 5, txt="", ln=False, border=0)
                    pdf.cell(45, 5, txt="POSTED BY", ln=False, align="C", border=0)
                    pdf.cell(22.5, 5, txt="", ln=False, border=0)
                    pdf.cell(45, 5, txt="CONFIRMED BY", ln=True, align="C", border=0)

                    file_name = f"GRN-{grn.grn_no}.pdf"
                    file = f"static/general/tmp/{file_name}"
                    pdf.output(file)
                    success_response['message'] = file

                elif module == 'print_issue':
                    issue = Issue.objects.get(id=data.get('id'))

                    from fpdf import FPDF
                    pdf = FPDF()
                    pdf.add_page()

                    pdf.set_font("Arial","",10)
                    pdf.cell(190, 5, txt="Sneda Smart Meters Limited", ln=True, border=0, align="C")
                    pdf.cell(190, 5, txt="P.O. Box 1024, Accra, Ghana", ln=True, border=0, align="C")
                    pdf.cell(190, 5, txt="Tel: +233 54 200 3000 / 55 505 9999", ln=True, border=0, align="C")
                    pdf.cell(190, 5, txt="Email: bharat@snedaghana.com", ln=True, border=0, align="C")
                    pdf.ln(10)

                    pdf.set_font("Arial","B", size=20)
                    pdf.cell(190, 5, txt="GOODS ISSUE WAYBILL", ln=True, border=0, align="C")
                    pdf.ln(10)

                    pdf.set_font("Arial","B", size=12)
                    pdf.cell(90, 5, txt=f"Document", ln=False, align="L",border=0)


                    pdf.set_font("Arial", "B", size=12)
                    pdf.cell(100, 5, txt="Contactor", ln=True, align="R",border=0)

                    pdf.set_font("Arial",'B', size=10)
                    pdf.cell(20, 5, txt=f"Entry: ", ln=False, align="L",border=0)
                    pdf.set_font("Arial",'', size=10)
                    pdf.cell(75, 5, txt=f"{issue.issue_no}", ln=False, align="L",border=0)

                    pdf.set_font("Arial",'B', size=10)
                    pdf.cell(75, 5, txt=f"", ln=False, align="R",border=0)
                    pdf.set_font("Arial",'', size=10)
                    pdf.cell(20, 5, txt=f"{issue.contractor.company}", ln=True, align="R",border=0)

                    pdf.set_font("Arial",'B', size=10)
                    pdf.cell(20, 5, txt=f"Date: ", ln=False, align="L",border=0)
                    pdf.set_font("Arial",'', size=10)
                    pdf.cell(75, 5, txt=f"{issue.issue_date}", ln=False, align="L",border=0)

                    pdf.set_font("Arial",'B', size=10)
                    pdf.cell(75, 5, txt=f"", ln=False, align="R",border=0)
                    pdf.set_font("Arial",'', size=10)
                    pdf.cell(20, 5, txt=f"{issue.contractor.owner}", ln=True, align="R",border=0)

                    pdf.set_font("Arial",'B', size=10)
                    pdf.cell(20, 5, txt=f"", ln=False, align="L",border=0)
                    pdf.set_font("Arial",'', size=10)
                    pdf.cell(75, 5, txt=f"", ln=False, align="L",border=0)

                    pdf.set_font("Arial",'B', size=10)
                    pdf.cell(75, 5, txt=f"Phone: ", ln=False, align="R",border=0)
                    pdf.set_font("Arial",'', size=10)
                    pdf.cell(20, 5, txt=f"{issue.contractor.phone}", ln=True, align="R",border=0)

                    pdf.set_font("Arial",'B', size=10)
                    pdf.cell(20, 5, txt=f"", ln=False, align="L",border=0)
                    pdf.set_font("Arial",'', size=10)
                    pdf.cell(75, 5, txt=f"", ln=False, align="L",border=0)

                    pdf.set_font("Arial",'B', size=10)
                    pdf.cell(75, 5, txt=f"Car No: ", ln=False, align="R",border=0)
                    pdf.set_font("Arial",'', size=10)
                    pdf.cell(20, 5, txt=f"{issue.car_no}", ln=True, align="R",border=0)

                    pdf.set_font("Arial",'B', size=10)
                    pdf.cell(20, 5, txt=f"", ln=False, align="L",border=0)
                    pdf.set_font("Arial",'', size=10)
                    pdf.cell(75, 5, txt=f"", ln=False, align="L",border=0)



                    pdf.ln(10)

                    pdf.set_font("Arial", "B", size=8)
                    pdf.cell(10, 5, txt="LN", ln=False, border=1, align="L")
                    pdf.cell(25, 5, txt="Barcode", ln=False, border=1, align="L")
                    pdf.cell(65, 5, txt="Name", ln=False, border=1, align="L")
                    pdf.cell(15, 5, txt="UOM", ln=False, border=1, align="C")
                    pdf.cell(15, 5, txt="Pak. Qty", ln=False, border=1, align="C")
                    pdf.cell(15, 5, txt="Qty", ln=False, border=1, align="C")
                    pdf.cell(15, 5, txt="Tot. Qty", ln=False, border=1, align="C")
                    pdf.cell(15, 5, txt="Rate", ln=False, border=1, align="C")
                    pdf.cell(15, 5, txt="Tot. Amt", ln=True, border=1, align="C")

                    pdf.set_font("Arial", size=8)
                    ln = 1
                    for transaction in IssueTransaction.objects.filter(issue=issue):
                        pdf.cell(10, 5, txt=str(ln), ln=False, border=1, align="L")
                        pdf.cell(25, 5, txt=transaction.barcode, ln=False, border=1, align="L")
                        pdf.cell(65, 5, txt=transaction.name[:60], ln=False, border=1, align="L")
                        pdf.cell(15, 5, txt=transaction.uom, ln=False, border=1, align="C")
                        pdf.cell(15, 5, txt=str(transaction.pack_qty), ln=False, border=1, align="C")
                        pdf.cell(15, 5, txt=str(transaction.qty), ln=False, border=1, align="C")
                        pdf.cell(15, 5, txt=str(transaction.total_qty), ln=False, border=1, align="C")
                        pdf.cell(15, 5, txt=str(transaction.rate), ln=False, border=1, align="C")
                        pdf.cell(15, 5, txt=str(transaction.amount), ln=True, border=1, align="C")
                        ln += 1

                    if Meter.objects.filter(issue=issue).exists():
                        pdf.multi_cell(190, 10, txt="Meters: [" + ', '.join([meter.meter_no for meter in Meter.objects.filter(issue=issue)]) + "]",border=True, align="L")
                    pdf.ln(10)

                    pdf.set_font("Arial", size=10)
                    pdf.cell(170, 5, txt="Total Amount: ", ln=False, align="R",border=0)
                    pdf.cell(20, 5, txt=str(issue.obj().get('total_amount')), ln=True, align="R",border=0)

                    pdf.set_font("Arial", size=10)
                    pdf.cell(170, 5, txt="Total Qty: ", ln=False, align="R",border=0)
                    pdf.cell(20, 5, txt=str(issue.obj().get('total_qty')), ln=True, align="R",border=0)

                    pdf.ln(10)
                    pdf.set_font("Arial", size=10)
                    pdf.cell(190 / 6, 10, txt=f"{issue.created_by.first_name} {issue.created_by.last_name}", ln=False, align="C",border=1)
                    pdf.cell(190 / 6, 10, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 12, 10, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 6, 10, txt=f"{issue.obj().get('posted_by')}", ln=False, align="C",border=1)
                    pdf.cell(190 / 12, 10, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 6, 10, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 6, 10, txt="", ln=True, align="R",border=1)

                    pdf.cell(190 / 6, 10, txt="Created By", ln=False, align="C",border=0)
                    pdf.cell(190 / 6, 10, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 12, 10, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 6, 10, txt="Posted By", ln=False, align="C",border=0)
                    pdf.cell(190 / 12, 10, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 6, 10, txt="", ln=False, align="R",border=0)
                    pdf.cell(190 / 6, 10, txt="Confirmed By", ln=True, align="C",border=0)

                    file_name = f"ISSUE-{issue.issue_no}.pdf"
                    file = f"static/general/tmp/{file_name}"
                    pdf.output(file)
                    success_response['message'] = file

                elif module == 'print_services':
                    from fpdf import FPDF
                    pdf = FPDF()
                    pdf.add_page()

                    pdf.set_font("Arial","B", size=12)
                    pdf.cell(190, 5, txt="Services", ln=True, border=0, align="C")
                    pdf.ln(10)


                    pdf.cell(20, 5, txt="Code", ln=False, align="L",border=0)
                    pdf.cell(50, 5, txt="Name", ln=False, align="L",border=0)
                    pdf.cell(50, 5, txt="Description", ln=False, align="L",border=0)
                    pdf.cell(20, 5, txt="Rate", ln=True, align="L",border=0)
                    pdf.ln(10)

                    services = Service.objects.all()
                    for service in services:
                        pdf.set_font("Arial","B", size=10)
                        pdf.cell(20, 5, txt=f"{service.code}", ln=False, align="L",border=0)
                        pdf.cell(50, 5, txt=f"{service.name}", ln=False, align="L",border=0)
                        pdf.cell(50, 5, txt=f"{service.description}", ln=False, align="L",border=0)
                        pdf.cell(20, 5, txt=f"{service.rate}", ln=True, align="L",border=0)
                        pdf.ln(5)

                    file_name = f"Services.pdf"
                    file = f"static/general/tmp/{file_name}"
                    pdf.output(file)
                    success_response['message'] = file



                elif module == 'issue':
                    id = data.get('id','*')
                    find_by = data.get('find_by','id')
                    if id == '*':
                        issues = Issue.objects.all()
                        success_response['message'] = [issue.obj() for issue in issues]
                    else:
                        if find_by == 'id':
                            issue = Issue.objects.get(id=id)
                        else:
                            issue = Issue.objects.get(issue_no=id)
                        success_response['message'] = issue.obj()

                elif module == 'issue_meters':
                    issue_id = data.get('id')
                    issue = Issue.objects.get(id=issue_id)
                    meters = Meter.objects.filter(issue=issue)
                    success_response['message'] = [meter.obj() for meter in meters]

                elif module == 'service_order':
                    id = data.get('id','*')
                    filter = data.get('filter','*')
                    status = data.get('status','pending')
                    print(data)
                    if id == '*':
                        service_orders = ServiceOrder.objects.all()[:10]
                        if filter == 'contractor':
                            limit = data.get('filter',1000)
                            service_orders = ServiceOrder.objects.filter(contractor=data.get('contractor'),status=status)
                            status = data.get('status')

                        elif filter == 'plot':
                            service_orders = ServiceOrder.objects.filter(plot=data.get('plot'))[:10]
                        elif filter == 'service_type':
                            service_orders = ServiceOrder.objects.filter(service_type=data.get('service_type'))[:10]

                        success_response['message'] = [service_order.obj() for service_order in service_orders]
                    else:
                        service_order = ServiceOrder.objects.filter(Q(id=id) | Q(new_meter=id)).first()
                        success_response['message'] = [service_order.obj()]



                elif module == 'service_order_item':
                    print(data)
                    service_order_id = data.get('service_order_id')
                    if service_order_id == '*':
                        service_order_items = ServiceOrderItem.objects.all()
                        success_response['message'] = [service_order_item.obj() for service_order_item in service_order_items]
                    else:
                        service_order_item = ServiceOrderItem.objects.get(id=service_order_id)
                        success_response['message'] = service_order_item.obj()

                elif module == 'service_order_return':
                    id = data.get('id')
                    if id == '*':
                        return_items = ServiceOrderReturns.objects.all()
                        success_response['message'] = [return_item.obj() for return_item in return_items]
                    else:
                        return_item = ServiceOrderReturns.objects.get(id=id)
                        success_response['message'] = return_item.obj()

                elif module == 'reedem':
                    pk = data.get('pk')
                    entry = Reedem.objects.get(pk=pk)

                    if pk == '*':
                        redeems = Reedem.objects.all()
                        success_response['message'] = [redeem.obj() for redeem in redeems]
                    else:
                        redeem = Reedem.objects.get(pk=pk)
                        success_response['message'] = redeem.obj()

                elif module == 'daily_report':
                    from django.utils import timezone
                    from datetime import datetime
                    from .models import ServiceOrder

                    day_date = data.get('date', datetime.now().date())
                    remarks = data.get('remarks', '')

                    from fpdf import FPDF

                    class MyPDF(FPDF):
                        def header(self):
                            # Header background
                            self.set_fill_color(44, 62, 80) # Dark Blue
                            self.rect(0, 0, 210, 40, 'F')

                            # Company Name
                            self.set_text_color(255, 255, 255)
                            self.set_font("Arial", "B", 16)
                            self.cell(0, 10, "SNEDA SMART METERS LTD", ln=True, align="C")

                            # Report Title
                            self.set_font("Arial", "", 12)
                            self.cell(0, 10, f"Daily Operational Report - {day_date}", ln=True, align="C")
                            self.ln(15)

                        def footer(self):
                            self.set_y(-15)
                            self.set_font("Arial", "I", 8)
                            self.set_text_color(128, 128, 128)
                            self.cell(0, 10, f"Page {self.page_no()} | Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", align="C")

                        def styled_table_header(self, headers, widths):
                            self.set_fill_color(52, 152, 219) # Light Blue
                            self.set_text_color(255, 255, 255)
                            self.set_font("Arial", "B", 10)
                            for i in range(len(headers)):
                                self.cell(widths[i], 8, headers[i], border=1, align="C", fill=True)
                            self.ln()
                            self.set_text_color(51, 51, 51)
                            self.set_font("Arial", "", 10)

                    pdf = MyPDF('P', 'mm', 'A4')
                    pdf.set_auto_page_break(auto=True, margin=15)
                    pdf.add_page()

                    for srv in ServiceOrder.objects.filter(service_date=day_date):

                        srv.custom_update()

                    # 0. add remarks in a modern card
                    pdf.set_font("Arial", "B", 12)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(0, 10, "Remarks", ln=True)
                    pdf.set_font("Arial", "", 10)
                    pdf.multi_cell(0, 6, remarks)
                    pdf.ln(10)

                    # 0. Phase Type
                    pdf.set_font("Arial", "B", 12)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(0, 10, "Summary by Phase Type", ln=True)

                    widths = [47.5, 47.5, 47.5,47.5]
                    headers = ["Phase Type", "Today Jobs", "Total Jobs","Stock *"]
                    pdf.styled_table_header(headers, widths)
                    fill = False
                    for phase in Phase.objects.all():
                        today_installed = phase.total_installed(day_date)
                        total_installed = phase.total_installed('*')
                        current_stock = phase.stock(day_date,'*')

                        pdf.set_fill_color(244, 247, 246) if fill else pdf.set_fill_color(255, 255, 255)
                        pdf.cell(widths[0], 7, f" {phase.description}", border=1, fill=True)
                        pdf.cell(widths[1], 7, f"{today_installed}", border=1, align="C", fill=True)
                        pdf.cell(widths[2], 7, f"{today_installed}", border=1, align="C", fill=True)
                        pdf.cell(widths[3], 7, f"{current_stock}", border=1, align="C", fill=True)
                        pdf.ln()
                        fill = not fill

                    pdf.ln(10)

                    # 0.1 Location Wise Report
                    pdf.set_font("Arial", "B", 12)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(0, 10, "Location Wise Stock Report", ln=True)

                    widths = [95, 47.5, 47.5]
                    headers = ["Location", "Phase", "Stock *"]
                    pdf.styled_table_header(headers, widths)
                    fill = False
                    for loc in Location.objects.all():
                        for phase in Phase.objects.all():
                            today_installed = phase.total_installed(day_date)

                            current_stock = phase.stock(day_date, loc.loc_id)

                            pdf.set_fill_color(244, 247, 246) if fill else pdf.set_fill_color(255, 255, 255)
                            pdf.cell(widths[0], 7, f" {loc.loc_name}", border=1, fill=True)
                            pdf.cell(widths[1], 7, f"{phase.description}", border=1, align="C", fill=True)
                            pdf.cell(widths[2], 7, f"{current_stock}", border=1, align="C", fill=True)
                            pdf.ln()
                            fill = not fill

                    pdf.ln(10)



                    # 1. SUMMARY BY SERVICE TYPE
                    pdf.set_font("Arial", "B", 12)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(0, 10, "Summary by Service Type", ln=True)

                    widths = [100, 45, 45]
                    headers = ["Service Type", "Today Jobs", "Total Jobs"]
                    pdf.styled_table_header(headers, widths)


                    total_today_jobs = 0
                    total_total_jobs = 0
                    fill = False

                    for st in ServiceType.objects.all():
                        today_jobs = st.today_jobs(day_date)
                        total_jobs = st.total_installations(day_date)

                        pdf.set_fill_color(244, 247, 246) if fill else pdf.set_fill_color(255, 255, 255)
                        pdf.cell(widths[0], 7, f" {st.name}", border=1, fill=True)
                        pdf.cell(widths[1], 7, f"{today_jobs}", border=1, align="C", fill=True)
                        pdf.cell(widths[2], 7, f"{total_jobs}", border=1, align="C", fill=True)
                        pdf.ln()

                        total_today_jobs += today_jobs
                        total_total_jobs += total_jobs
                        fill = not fill

                    # Total Row
                    pdf.set_font("Arial", "B", 10)
                    pdf.set_fill_color(230, 230, 230)
                    pdf.cell(widths[0], 8, " TOTAL", border=1, fill=True)
                    pdf.cell(widths[1], 8, f"{total_today_jobs}", border=1, align="C", fill=True)
                    pdf.cell(widths[2], 8, f"{total_total_jobs}", border=1, align="C", fill=True)
                    pdf.ln(10)

                    # 2. CONTRACTOR ON SITE
                    pdf.set_font("Arial", "B", 12)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(0, 10, "Contractors On Site", ln=True)

                    widths = [100, 45, 45]
                    headers = ["Contractor", "Today Jobs", "Total Jobs"]
                    pdf.styled_table_header(headers, widths)

                    c_total_today_jobs = 0
                    c_total_total_jobs = 0
                    fill = False

                    for contractor in Contractor.objects.filter(is_installer=True).order_by('company'):
                        today_jobs = ServiceOrder.objects.filter(contractor=contractor, service_date=day_date).count()
                        total_jobs = ServiceOrder.objects.filter(contractor=contractor, service_date__lte=day_date).count()

                        if today_jobs > 0:
                            pdf.set_fill_color(244, 247, 246) if fill else pdf.set_fill_color(255, 255, 255)
                            pdf.cell(widths[0], 7, f" {contractor.company[:40]}", border=1, fill=True)
                            pdf.cell(widths[1], 7, f"{today_jobs}", border=1, align="C", fill=True)
                            pdf.cell(widths[2], 7, f"{total_jobs}", border=1, align="C", fill=True)
                            pdf.ln()

                            c_total_today_jobs += today_jobs
                            c_total_total_jobs += total_jobs
                            fill = not fill

                    # Total Row
                    pdf.set_font("Arial", "B", 10)
                    pdf.set_fill_color(230, 230, 230)
                    pdf.cell(widths[0], 8, " TOTAL ON SITE", border=1, fill=True)
                    pdf.cell(widths[1], 8, f"{c_total_today_jobs}", border=1, align="C", fill=True)
                    pdf.cell(widths[2], 8, f"{c_total_total_jobs}", border=1, align="C", fill=True)
                    pdf.ln(10)

                    # 3. CONTRACTOR NOT ON SITE
                    pdf.set_font("Arial", "B", 12)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(0, 10, "Contractors Not On Site", ln=True)

                    widths = [100, 90]
                    headers = ["Contractor", "Phone Number"]
                    pdf.styled_table_header(headers, widths)

                    fill = False
                    for contractor in Contractor.objects.filter(is_installer=True).order_by('company'):
                        today_jobs = ServiceOrder.objects.filter(contractor=contractor, service_date=day_date).count()
                        if today_jobs <= 0:
                            pdf.set_fill_color(244, 247, 246) if fill else pdf.set_fill_color(255, 255, 255)
                            pdf.cell(widths[0], 7, f" {contractor.company[:40]}", border=1, fill=True)
                            pdf.cell(widths[1], 7, f" {contractor.phone}", border=1, fill=True)
                            pdf.ln()
                            fill = not fill
                    pdf.ln(10)

                    # 4. CONTRACTOR ERRORS
                    pdf.set_font("Arial", "B", 12)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(0, 10, "Contractor Quality Control (Errors)", ln=True)

                    widths = [100, 45, 45]
                    headers = ["Contractor", "Errors", "Weekly Margin"]
                    pdf.styled_table_header(headers, widths)

                    total_errors = 0
                    fill = False
                    for contractor in Contractor.objects.filter(is_installer=True).order_by('company'):
                        errors = ContractorError.objects.filter(contractor=contractor)
                        if errors.exists():
                            total_errors += errors.count()
                            week_limit = contractor.error_limit()['week']
                            error_margin = f"{(errors.count() / week_limit * 100):.2f}%" if week_limit > 0 else "0.00%"

                            pdf.set_fill_color(244, 247, 246) if fill else pdf.set_fill_color(255, 255, 255)
                            pdf.cell(widths[0], 7, f" {contractor.company[:40]}", border=1, fill=True)
                            pdf.cell(widths[1], 7, f"{errors.count()}", border=1, align="C", fill=True)
                            pdf.cell(widths[2], 7, f"{error_margin}", border=1, align="C", fill=True)
                            pdf.ln()
                            fill = not fill

                    # Total Row
                    pdf.set_font("Arial", "B", 10)
                    pdf.set_fill_color(230, 230, 230)
                    pdf.cell(widths[0], 8, " TOTAL ERRORS", border=1, fill=True)
                    pdf.cell(widths[1] + widths[2], 8, f"{total_errors}", border=1, align="C", fill=True)
                    pdf.ln(10)

                    # 5. ISSUED MATERIALS
                    pdf.set_font("Arial", "B", 12)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(0, 10, "Issued Materials Today", ln=True)

                    widths = [80, 30, 40, 40]
                    headers = ["Material", "Qty", "Est. Value", "Total Amt"]
                    pdf.styled_table_header(headers, widths)

                    total_amt = 0
                    total_qty = 0
                    fill = False

                    materials_data = IssueTransaction.objects.filter(issue__issue_date=day_date, issue__issue_type='ISS')
                    from django.db.models import Sum

                    # Group by material
                    unique_materials = InventoryMaterial.objects.filter(barcode__in=materials_data.values_list('barcode', flat=True))
                    for material in unique_materials:
                        qty = materials_data.filter(material=material).aggregate(t_qty=Sum('total_qty'))['t_qty'] or 0
                        amount = qty * material.value

                        pdf.set_fill_color(244, 247, 246) if fill else pdf.set_fill_color(255, 255, 255)
                        pdf.cell(widths[0], 7, f" {material.name[:35]}", border=1, fill=True)
                        pdf.cell(widths[1], 7, f"{qty}", border=1, align="C", fill=True)
                        pdf.cell(widths[2], 7, f"{'{:,.2f}'.format(material.value)}", border=1, align="R", fill=True)
                        pdf.cell(widths[3], 7, f"{'{:,.2f}'.format(amount)} ", border=1, align="R", fill=True)
                        pdf.ln()

                        total_amt += amount
                        total_qty += qty
                        fill = not fill

                    # Total Row
                    pdf.set_font("Arial", "B", 10)
                    pdf.set_fill_color(230, 230, 230)
                    pdf.cell(widths[0], 8, " TOTAL ISSUED", border=1, fill=True)
                    pdf.cell(widths[1], 8, f"{total_qty}", border=1, align="C", fill=True)
                    pdf.cell(widths[2], 8, "", border=1, fill=True)
                    pdf.cell(widths[3], 8, f"{'{:,.2f}'.format(total_amt)} ", border=1, align="R", fill=True)
                    pdf.ln(10)

                    # 6. METERS INSTALLED TODAY
                    pdf.add_page() # Start on new page if needed, or just let auto-page-break handle it
                    pdf.set_font("Arial", "B", 12)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(0, 10, "Detailed Meter Installations Today", ln=True)

                    widths = [10, 25, 55, 30, 70]
                    headers = ["#", "Meter No", "Customer", "Mobile", "Contractor"]
                    pdf.styled_table_header(headers, widths)
                    pdf.set_font("Arial", "", 8)

                    meters = ServiceOrder.objects.filter(service_date=day_date).order_by('contractor__company')
                    fill = False
                    for i, meter in enumerate(meters, 1):
                        pdf.set_fill_color(244, 247, 246) if fill else pdf.set_fill_color(255, 255, 255)
                        pdf.cell(widths[0], 6, f"{i}", border=1, align="C", fill=True)
                        pdf.cell(widths[1], 6, f" {meter.new_meter}", border=1, fill=True)
                        pdf.cell(widths[2], 6, f" {meter.customer[:30]}", border=1, fill=True)
                        pdf.cell(widths[3], 6, f" {meter.customer_no}", border=1, fill=True)
                        pdf.cell(widths[4], 6, f" {meter.contractor.company[:45]}", border=1, fill=True)
                        pdf.ln()
                        fill = not fill

                    file_name = f"Daily_Report_{day_date}.pdf"
                    file_path = f"static/general/tmp/{file_name}"
                    pdf.output(file_path)
                    success_response['message'] = file_path


                elif module == 'item_availability':
                    from django.utils import timezone

                    as_of = data.get('as_of_field   ',timezone.now().date())
                    loc_id = data.get('location','*')
                    stock_only = data.get('stock_only','no')
                    re_order = data.get('re_order','NO')
                    print(data)
                    if stock_only == 'yes':
                        stock_only = True
                    else:
                        stock_only = False

                    print(data)
                    print(as_of)
                    arr = []

                    import openpyxl
                    book = openpyxl.Workbook()
                    sheet = book.active
                    sheet.title = f"Item Availability {as_of}"
                    sheet.append(["NAME","TOTAL IN","TOTAL OUT","BALANCE","RE-ORDER QTY"])

                    from fpdf import FPDF
                    pdf = FPDF('P','mm','A4')
                    pdf.add_page()
                    pdf.set_font("Arial","B", size=12)
                    pdf.cell(190, 5, txt=f"Item Availability {as_of}", ln=True, border=0, align="C")
                    pdf.ln(10)

                    pdf.set_font("Arial","B", size=10)
                    pdf.cell(100, 5, txt="Material", ln=False, align="L",border=1)
                    pdf.cell(25, 5, txt="Total In", ln=False, align="L",border=1)
                    pdf.cell(30, 5, txt="Total Out", ln=False, align="L",border=1)
                    pdf.cell(30, 5, txt="Balance", ln=True, align="L",border=1)

                    pdf.set_font("Arial","", size=10)

                    total = 0
                    tq = 0
                    total_value = 0

                    materials = InventoryMaterial.objects.all().order_by('name')
                    for material in materials:

                        in_and_out = material.in_and_out(as_of,loc_id)
                        print("#" * 4)
                        print(in_and_out)
                        print("#" * 4)

                        total_qty = material.stock(as_of,loc_id)
                        print(total_qty,as_of,loc_id)
                        ql = False
                        if stock_only :
                            if total_qty > 0:
                                ql = True
                            else:
                                ql = False
                        else:
                            ql = True

                        if ql:
                            total_amount = total_qty * material.value
                            # pdf.cell(100, 5, txt=f"{material.name[:30]}", ln=False, align="L",border=1)
                            # pdf.cell(25, 5, txt=f"{in_and_out.get('in_trans')}", ln=False, align="L",border=1)
                            # pdf.cell(30, 5, txt=f"{'{:,.2f}'.format(in_and_out.get('out_trans'))}", ln=False, align="L",border=1)
                            # pdf.cell(30, 5, txt=f"{'{:,.2f}'.format(in_and_out.get('balance'))}", ln=True, align="L",border=1)

                            if re_order == 'YES':
                                if material.reorder_qty > in_and_out.get('balance'):
                                    pdf.set_font("Arial","B", size=10)
                                    pdf.cell(100, 5, txt=f"{material.name[:30]}", ln=False, align="L",border=1)
                                    pdf.cell(25, 5, txt=f"{in_and_out.get('in_trans')}", ln=False, align="L",border=1)
                                    pdf.cell(30, 5, txt=f"{'{:,.2f}'.format(in_and_out.get('out_trans'))}", ln=False, align="L",border=1)
                                    pdf.cell(30, 5, txt=f"{'{:,.2f}'.format(in_and_out.get('balance'))}", ln=True, align="L",border=1)

                                    sheet.append([
                                        material.name,in_and_out.get('in_trans'),in_and_out.get('out_trans'),in_and_out.get('balance')
                                    ])
                            else:
                                pdf.set_font("Arial","B", size=10)
                                pdf.cell(100, 5, txt=f"{material.name[:30]}", ln=False, align="L",border=1)
                                pdf.cell(25, 5, txt=f"{in_and_out.get('in_trans')}", ln=False, align="L",border=1)
                                pdf.cell(30, 5, txt=f"{'{:,.2f}'.format(in_and_out.get('out_trans'))}", ln=False, align="L",border=1)
                                pdf.cell(30, 5, txt=f"{'{:,.2f}'.format(in_and_out.get('balance'))}", ln=True, align="L",border=1)
                                sheet.append([
                                        material.name,in_and_out.get('in_trans'),in_and_out.get('out_trans'),in_and_out.get('balance'),material.reorder_qty
                                    ])

                            total += total_amount
                            tq += total_qty
                            total_value += material.value

                            arr.append({
                                'name':material.name,
                                'stock_qty':total_qty,
                                'value':material.value,
                                'total_amount':total_amount,
                                'in_out':in_and_out
                            })

                    xfile = f"static/general/tmp/{as_of}.xlsx"
                    book.save(xfile)
                    file_name = f"Item Availability As Of {as_of}.pdf"
                    file = f"static/general/tmp/{file_name}"
                    pdf.output(file)
                    success_response['message'] = {
                        'file':xfile,
                        'data':arr
                    }



                elif module == 'contractor_wise':
                    from django.utils import timezone
                    from datetime import timedelta
                    arr = []
                    pass

                    success_response['message'] = arr


                else:
                    success_response['status_code'] = 400
                    success_response['message'] = f"Module Not Found {module}"



                response = success_response
        elif method == 'DELETE':
            if module == 'service':
                id = data.get('id')
                service = Service.objects.get(id=id)
                service.delete()
                success_response['message'] = "Service Deleted Successfully"

            elif module == 'compliance':
                print(data)
                pk = data.get('pk')
                remarks = data.get('remarks')

                cp = FocCompliance.objects.get(pk=pk)
                email = cp.foc.email
                phone = cp.foc.phone

                name = cp.c_type.name

                sms = f"Your compliance ({name}) has been rejected with remarks:\n\n{remarks}\nPlease Re-upload again"
                cp.delete()
                # send sms
                Sms.objects.create(
                    api=SmsApi.objects.get(is_default=True),
                    to=phone,
                    message=sms
                )
                success_response['message'] = "Compliance Deleted Successfully"

            elif module == 'foc_invoice':
                FocInvoiceHd.objects.get(entry_no=data.get('entry_no')).delete()
                success_response['message'] = "Invoice Deleted Successfully"

            elif module == "service_type":
                print(data)
                ServiceType.objects.get(pk=data.get('pk')).delete()
                success_response['message'] = "Service Type Deleted Successfully"

            elif module == 'delete_transfer':
                entry_no = data.get('entry_no')
                transfer = TransferHd.objects.get(entry_no=entry_no)
                actor = User.objects.get(pk=data.get('mypk'))


                
                TransferTr.objects.filter(entry=transfer).delete()
                Cardex.objects.filter(
                        doc_type='TRF',
                        doc_no=entry_no
                    ).delete()
                rm = transfer.remarks
                transfer.remarks = f"Deleted By {actor.username} | {rm}"
                transfer.is_valid = False
                transfer.is_sent=False
                transfer.is_posted=False
                transfer.sent_by = None
                transfer.approved_by = None
                transfer.car_no = ""
                transfer.transporter = ""

                transfer.save()
                success_response['message'] = "Transfer Deleted"
                response = success_response


            elif module == 'meter':
                id = data.get('id')
                meter = Meter.objects.get(id=id)
                meter.delete()
                success_response['message'] = "Meter Deleted Successfully"

            elif module == 'order_service':
                id = data.get('id')
                service_order_item = ServiceOrderItem.objects.get(id=id)
                service_order_item.delete()
                success_response['message'] = "Service Order Item Deleted Successfully"

            elif module == 'service_order':
                id = data.get('id')
                service_order = ServiceOrder.objects.get(id=id)
                meter_no = service_order.new_meter
                meter = Meter.objects.get(meter_no=meter_no)
                meter.is_issued = False
                meter.contractor = Contractor.objects.get(company='A TRADITION')
                meter.save()
                service_order.delete()
                success_response['message'] = "Service Order Deleted Successfully"

            elif module == 'issue':
                id = data.get('id')
                issue = Issue.objects.get(id=id)
                # delete transactions
                IssueTransaction.objects.filter(issue=issue).delete()
                issue.is_deleted = True
                issue.save()
                success_response['message'] = "Issue Deleted Successfully"

            elif module == 'grn':
                id = data.get('id')
                grn = Grn.objects.get(id=id)
                # delete transactions
                GrnTransaction.objects.filter(grn=grn).delete()
                Cardex.objects.filter(doc_no=grn.grn_no,doc_type='GR').delete()
                grn.is_deleted = True
                grn.save()
                success_response['message'] = "GRN Deleted Successfully"

            elif module == 'service_material':
                id = data.get('id')
                MaterialOrderItem.objects.get(id=id).delete()
                success_response['message'] = "Material Deleted"

            elif module == 'linked_service':
                id = data.get('id')
                ServiceMaterials.objects.get(id=id).delete()
                success_response['message'] = "Service Deleted"

            elif module == 'service_order_return':
                id = data.get('id')
                ServiceOrderReturns.objects.get(id=id).delete()
                success_response['message'] = "Return Deleted"

            elif module == 'reedem':
                id = data.get('id')
                redeem = Reedem.objects.get(id=id)
                RedeemTransactions.objects.filter(redeem=redeem).delete()
                redeem.is_valid = False
                redeem.save()

                success_response['message'] = "Reedem Deleted"

            elif module == 'material':
                id = data.get('id')
                material = InventoryMaterial.objects.get(id=id)

                # check cardex
                cardex = Cardex.objects.filter(material=material).aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0
                if cardex > 0:
                    success_response['status_code'] = 400
                    success_response['message'] = "Material Cannot Be Deleted"
                else:
                    material.delete()
                    success_response['message'] = "Material Deleted"

            else:
                success_response['status_code'] = 400
                success_response['message'] = f"Module Not Found {module}"
        
        elif method == 'PATCH':
            if module == 'material':
                
                barcode = data.get('barcode')
                name = data.get('name')
                group = InventoryGroup.objects.get(id=data.get('group'))
                reorder_qty = data.get('reorder_qty')
                value = data.get('value')
                is_return = data.get('is_return')
                is_issue = data.get('is_issue')
                auto_issue = data.get('auto_issue')
                item_type = data.get('item_type')
                required_qty = data.get('required_qty')

                print(data)
                
                print(data)
                material = InventoryMaterial.objects.get(barcode=barcode)
                material.name = name
                material.group = group
                material.reorder_qty = reorder_qty
                material.value = value
                material.item_type = item_type
                material.is_return = is_return
                material.is_issue = is_issue
                material.issue_qty = data.get('issue_qty')
                material.auto_issue = auto_issue
                material.required_qty = required_qty


                material.save()
                success_response['message'] = "Material Updated Successfully"

            elif module == 'validate_foc_invoice':
                entry_no = data.get('entry_no')
                invoice = FocInvoiceHd.objects.get(entry_no=entry_no)
                validated_by = User.objects.get(pk=data.get('mypk'))
                foc = invoice.foc

                rows_html = """
                    <tr>
                        <th>SN</th>
                        <th>Item</th>
                        <th>Quantity</th>
                        <th>Rate</th>
                        <th>Amount</th>
                    </tr>
                """

                trsn = 1
                for row in invoice.trans():
                    rows_html += f"""
                        <tr>
                            <td>{trsn}</td>
                            <td>{row.get('item')}</td>
                            <td>{row.get('quantity')}</td>
                            <td>{row.get('rate')}</td>
                            <td>{row.get('amount')}</td>
                        </tr>
                    """
                    trsn += 1

                html_body = f"""
                    Dear {foc.company}, an Invoice has been issued to your company, please accept it in FOC Node app for payment to begin. You can also reject it with remarks
                    Invoice: {invoice.entry_no}
                    Gross: {invoice.gross_amount}
                    Tax: {invoice.tax_amount}
                    Net: {invoice.net_amount}
                    
                    {rows_html}
                    
                    Note: Without required compliance document, net will be paid to you, else, we will pay the whole gross and hold onto 6% for administrative cost
                    
                """

                sms = f"Dear {foc.company}, and invoice has been raised to your company with remarks: {invoice.remarks}. Please accept or reject with the FOC Node App"

                # Que Mail
                MailQueues.objects.create(
                    sender=MailSenders.objects.get(is_default=True),
                    recipient=foc.email,
                    cc='',
                    body=html_body,
                    mail_key=make_md5_hash(invoice.remarks),
                    subject=f"SNEDA - {invoice.remarks}",
                )

                # send sms
                Sms.objects.create(
                    api=SmsApi.objects.get(is_default=True),
                    to=foc.phone,
                    message=sms
                )

                invoice.is_valid = True
                invoice.validated_by = validated_by
                from django.utils import timezone
                date_validated=timezone.now().date()
                invoice.save()

                success_response['message'] = "Invoice Validated Successfully"



            elif module == 'prop_patch':
                # update service materials
                barcodes = {
                    '1': ['MT022', 'MT020', 'MT019', 'MT018'],  # User card, CIU, Enclosure, Meter
                    '3': ['MT063', 'MT062', 'MAT-38', 'MT061'],  # User card, CIU, Enclosure, Meter
                }
                for service in ServiceOrder.objects.all():
                    sts = service.new_meter
                    #MaterialOrderItem
                    phase = service.linked_phase
                    phase_no = 0
                    if phase:
                        phase_no = phase.number
                    if phase_no != 0:
                        print(sts,phase_no)
                        materials = barcodes.get(phase_no)
                        if materials is not None:
                            for barcode in materials:
                                mt = InventoryMaterial.objects.get(barcode=barcode)
                                try:
                                    MaterialOrderItem.objects.create(
                                        service_order=service,
                                        material=mt,
                                        quantity=1,
                                        rate=0,
                                        amount=0,
                                        material_type='is'

                                    )
                                    print(mt.name,"Added to",sts)
                                except Exception as e:
                                    print(str(e))
                        else:
                            print(phase_no, "has no materials")

                    else:
                        print(f"No Phase {sts}")



                    # service.custom_update()

            elif module == 'post_foc_invoice':

                entry_no = data.get('entry_no')
                invoice = FocInvoiceHd.objects.get(entry_no=entry_no)
                invoice.update_totals()
                posted_by = User.objects.get(pk=data.get('mypk'))

                #JVHeader.objects.all().delete()

                # check if invoice is ready to post
                if not invoice.is_valid:
                    raise Exception("Invoice is not valid")

                # check if foc accepted invoice
                if not invoice.is_accepted:
                    raise Exception("Invoice is not accepted")


                # write to ledger
                foc = invoice.foc
                if SubLedger.objects.filter(code=foc.code).count() == 0:
                    # create ledger

                    SubLedger.objects.create(
                        code=foc.code,
                        name=f"FOC - {foc.company}",
                        description=f"Ledger for {foc.company} installations",
                        owner=posted_by,
                        ledger=Ledger.objects.get(sledge='all_payable')
                    )

                foc_ledger = SubLedger.objects.get(code=foc.code)


                # create JV
                jv_entry_no = generate_entry_entry('JV')
                JVHeader.objects.create(
                    date=invoice.invoice_date,
                    narration=invoice.remarks,
                    prepared_by=posted_by,
                    ref=invoice.entry_no,
                    voucher_no=jv_entry_no

                )

                jv = JVHeader.objects.get(voucher_no=jv_entry_no)
                for it in FocInvoiceTransactions.objects.filter(invoice=invoice):
                    item = it.item
                    quantity = it.quantity
                    rate = it.rate
                    amount = it.net_amount

                    JVTransaction.objects.create(
                        header=jv,
                        sub_ledger=foc_ledger,
                        ledger=foc_ledger.ledger,
                        credit=amount,
                        created_by=posted_by,
                        line_description=f"{item}: {rate} * {quantity}"
                    )

                # write tax ledger


                vatledge = Ledger.objects.get(sledge='vat')

                JVTransaction.objects.create(
                    header=jv,
                    ledger=vatledge,
                    credit=invoice.tax_amount,
                    created_by=posted_by,
                    line_description=f"Vat to pay on {invoice.remarks}"
                )

                # record expense
                exp_ledge = Ledger.objects.get(sledge='foc_install_expense')
                JVTransaction.objects.create(
                    header=jv,
                    ledger=exp_ledge,
                    debit=invoice.gross_amount,
                    created_by=posted_by,
                    line_description=f"Installation Cost: {invoice.remarks}"
                )

                from django.utils import timezone
                invoice.is_posted = True
                invoice.posted_by = posted_by
                invoice.date_posted = timezone.now().date()
                invoice.save()

                success_response['message'] = 'Invoice Posted Successfully'


            elif module == 'installation_type':
                id = data.get('id')
                installation_type = InstallationType.objects.get(pk=id)
                installation_type.name = data.get('edit_name')
                installation_type.description = data.get('edit_description')
                installation_type.save()

                phase_rates = data.get('phase_rates')
                for phase_rate in phase_rates:
                    phase = Phase.objects.get(number=phase_rate.get('phase'))
                    if InstallationTypePhaseRate.objects.filter(
                        installation_type=installation_type,
                        phase=phase
                    ).exists():
                        InstallationTypePhaseRate.objects.filter(
                            installation_type=installation_type,
                            phase=phase
                        ).update(
                            rate=phase_rate.get('rate')
                        )
                    else:
                        InstallationTypePhaseRate.objects.create(
                            installation_type=installation_type,
                            phase=phase,
                            rate=phase_rate.get('rate')
                        )


                success_response['message'] = "Installation Type Updated Successfully"

            elif module == 'set_expense_to_zero':
                pk = data.get('pk')
                expense = Expense.objects.get(pk=pk)
                if expense.amount == 0:
                    raise Exception("Cannot Reset 0")
                ori_amount = expense.amount
                expense.amount = data.get('amount',0)
                expense.ori_amount = ori_amount
                expense.save()

                response = success_response


            elif module == 'meter_phase':
                # INSERT_YOUR_CODE
                # PATCH method for 'meter_phase'
                """
                Update phase for all meters with a linked_phase, using the description
                from the current linked Phase to find and re-link to the Phase with the same description.
                """

                # add meters from services
                all_services = ServiceOrder.objects.all()
                srv_count = all_services.count()
                srv_s = 1
                for service in all_services:
                    meter_no = service.new_meter

                    # INSERT_YOUR_CODE
                    if not Meter.objects.filter(meter_no=meter_no).exists():
                        
                        try:
                            Meter.objects.create(
                                meter_no=meter_no,
                                ip_address=service.spn,
                                location=service.location,
                                created_by=request.user,
                                installation_address=service.spn,
                                phase=service.phase,
                                contractor=service.contractor,
                                is_issued=True,
                            )
                            print("adding_met",srv_s,'/',srv_count)
                        except Exception as e:
                            print("adding_met",srv_s,'/',srv_count,"ERR:",str(e))

                    
                    srv_s += 1
               

                meters = Meter.objects.all()
                updated_count = 0
                antop = 1
                all_count = meters.count()
                for meter in meters:
                    print(antop,'/',all_count)
                    antop += 1
                    # Find the Phase with the same description
                    meter_phase = meter.phase
                    print("PHASE FIRST",meter_phase)
                    if meter_phase == 'others':
                        # get phase from service
                        meter_phase = ServiceOrder.objects.filter(new_meter=meter_no).first().phase
                    

                    print(meter.meter_no,meter_phase)
                    # INSERT_YOUR_CODE
                    first_char = meter_phase[0] if meter_phase else ''
                    print("First character of meter_phase:", first_char)

                    phase_by_desc = Phase.objects.filter(number=first_char).order_by('id').first()
                    if phase_by_desc and meter.linked_phase_id != phase_by_desc.id:
                        meter.linked_phase = phase_by_desc
                        meter.save()
                        updated_count += 1

                success_response['message'] = f"Updated linked_phase for {updated_count} meters by phase description"
                response = success_response

            elif module == 'clear_contractor_error':
                from django.utils import timezone
                pk = data.get('pk')
                user = User.objects.get(pk=data.get('mypk'))
                remarks = data.get('remarks')

                ContractorError.objects.filter(pk=pk).update(
                    is_cleared=True,
                    cleared_by=user,
                    cleared_remarks=remarks,
                    cleared_at=timezone.now()
                )
                success_response['message'] = "Contractor Error Cleared Successfully"
                response = success_response

            elif module == 'location_default':
                print(data)
                Location.objects.all().update(is_default=False)
                lc = Location.objects.get(id=data.get('id'))
                lc.is_default = True
                lc.save()

                response = success_response

            elif module == 'stock_transfer':
                print(data)
                source = data.get('source')
                desination = data.get('destination')

                sr_prod = InventoryMaterial.objects.get(barcode=source)
                des_prod = InventoryMaterial.objects.get(barcode=desination)

                # Use try/except for each update to ensure one failure doesn't stop the rest
                try:
                    GrnTransaction.objects.filter(material=sr_prod).update(material=des_prod)
                except Exception as e:
                    print(f"Error updating GrnTransaction: {e}")
                try:
                    IssueTransaction.objects.filter(material=sr_prod).update(material=des_prod)
                except Exception as e:
                    print(f"Error updating IssueTransaction: {e}")
                try:
                    TransferTr.objects.filter(material=sr_prod).update(material=des_prod)
                except Exception as e:
                    print(f"Error updating TransferTr: {e}")
                try:
                    RequiredReturn.objects.filter(material=sr_prod).update(material=des_prod)
                except Exception as e:
                    print(f"Error updating RequiredReturn: {e}")
                try:
                    RedeemTransactions.objects.filter(material=sr_prod).update(material=des_prod)
                except Exception as e:
                    print(f"Error updating RedeemTransactions: {e}")
                try:
                    ServiceOrderReturns.objects.filter(material=sr_prod).update(material=des_prod)
                except Exception as e:
                    print(f"Error updating ServiceOrderReturns: {e}")
                try:
                    MaterialOrderItem.objects.filter(material=sr_prod).update(material=des_prod)
                except Exception as e:
                    print(f"Error updating MaterialOrderItem: {e}")
                try:
                    ServiceMaterials.objects.filter(material=sr_prod).update(material=des_prod)
                except Exception as e:
                    print(f"Error updating ServiceMaterials: {e}")
                try:
                    IssueTransaction.objects.filter(material=sr_prod).update(material=des_prod)
                except Exception as e:
                    print(f"Error updating IssueTransaction (2nd): {e}")
                try:
                    Cardex.objects.filter(material=sr_prod).update(material=des_prod)
                except Exception as e:
                    print(f"Error updating Cardex: {e}")

                if data.get('delete') == 'YES':
                    sr_prod.delete()
                

                # for tr in Cardex.objects.filter(material=sr_prod):
                #     dis = tr.obj()
                #     doc_type = dis.get('doc_type')

                #     doc_type_choices = [
                #         ('GR', 'GRN'), # IN
                #         ('ISS', 'ISSUE'), # OUT
                #         ('CIS', 'Contractor Issue Return'), # IN
                #         ('RET', 'RETURN'), # IN
                #         ('TRF',"Transfer")# IN OUT
                #     ]
                #     if doc_type == 'GR':
                #         GrnTransaction.objects.filter(entry_no=dis.get('doc_no'),material=sr_prod)
                #     print(dis)

            elif module == 'approve_expense':
                pk = data.get('pk','*')
                print(data)
                if pk == '*':
                    expenses = Expense.objects.filter(is_approved=False)
                else:
                    expenses = Expense.objects.filter(id=pk)
                for expense in expenses:

                    
                    owner = expense.created_by
                    owner_email = owner.email

                    # Compose email subject and body for approving expense
                    subject = f"Expense Approved: {expense.category} - {expense.amount}"
                    body = (
                        f"Dear {owner.get_full_name()},\n\n"
                        f"Your expense request has been approved.\n\n"
                        f"Details:\n"
                        f"Category: {expense.category}\n"
                        f"Amount: {expense.amount}\n"
                        f"Reference: {expense.reference}\n"
                        f"Description: {expense.description}\n"
                        f"Date: {expense.date}\n\n"
                        f"Thank you."
                    )

                    expense.is_approved = True
                    expense.save()

                    if MailSenders.objects.filter(address='solomon@snedaghana.com').exists():
                        sender = MailSenders.objects.get(address='solomon@snedaghana.com')
                    else:
                        sender = MailSenders.objects.get(is_default=True)

                    mail = MailQueues(sender=sender, subject=subject, body=body,
                                                recipient='solomon@snedaghana.com',
                                                cc='',mail_key=make_md5_hash(f"{subject}{body}"))
                    mail.save()

            elif module == 'reject_expense':
                pk = data.get('pk','*')
                
                expenses = Expense.objects.get(id=pk)
                expenses.is_rejected = True
                expenses.save()
                success_response['message'] = "Expense Rejected Successfully"
                response = success_response

            elif module == 'update_cardex_tally':
                from django.db.models import Sum
                for material in InventoryMaterial.objects.all():
                    cardex_items = Cardex.objects.filter(material=material)
                    for ci in cardex_items:
                        created_at = ci.created_at
                        # get sum of material including this
                        # Get sum of material in cardex before this transaction including this
                        sum_qty = Cardex.objects.filter(
                            material=material,
                            created_at__lte=created_at
                        ).order_by('created_at').aggregate(total_qty=Sum('qty'))['total_qty'] or 0
                        ci.balance = sum_qty

                        print(material.name,"SET TO",sum_qty)
                        ci.save()

                response = success_response

            elif module == 'send_transfer':
                from django.utils import timezone
                entry_no = data.get('entry_no')
                car_no = data.get('car_no')
                driver = data.get('driver')
                mypk = data.get('mypk')

                sender = User.objects.get(pk=mypk)
                entry = TransferHd.objects.get(entry_no=entry_no)
                entry.is_sent = True
                entry.sent_by = sender
                entry.sent_date = timezone.now()
                entry.transporter = driver
                entry.car_no = car_no
                entry.save()

                success_response['message'] = "Transfer Sent"
                response = success_response


            elif module == 'update_return_as_of':
                tot = 0
                for service in ServiceOrder.objects.all():
                    
                    if RequiredReturn.objects.filter(service_type=service.service_type).exists():
                        
                        for record in RequiredReturn.objects.filter(service_type=service.service_type):
                            print(service.new_meter,record.service_type.name,"QUALIFIED")
                            try:
                                ServiceOrderReturns.objects.create(
                                    service_order=service,
                                    material=record.material,
                                    quantity=record.quantity,
                                    created_at=service.created_at,
                                    created_by=service.created_by

                                )
                                tot += 1
                            except Exception as e:
                                print(e)
                                pass
                    else:
                        print(service.new_meter,service.service_type.name,"NOT QUALIFIED")

                success_response['message'] = f"{tot} jobs updated"

            elif module == 'patch_locations':
                raise Exception("Disabled")
                #  Add field location to cardex
                location=Location.objects.get(loc_id='002')
                Cardex.objects.all().update(
                    location=location
                )
                # + Add field location to grn
                Grn.objects.all().update(
                    location=location
                )
                # + Add field location to issue
                Issue.objects.all().update(
                    location=location
                )
                # + Add field location to meter
                Meter.objects.all().update(
                    location=location
                )
                # + Add field location to reedem
                Reedem.objects.all().update(
                    location=location
                )
                # + Add field location to serviceorder
                ServiceOrder.objects.all().update(
                    location=location
                )

                success_response['message'] = "Default Locations Updated"


            elif module == 'meter_remove_issue':
                id = data.get('id')
                meter = Meter.objects.get(id=id)
                meter.is_issued = False
                meter.service_order = None
                meter.save()
                success_response['message'] = "Meter Updated Successfully"

            elif module == 'issue_meter':
                id = data.get('id')
                meter = Meter.objects.get(id=id)
                
                if data.get('status') == 'unassigned':
                    meter.is_issued = False
                    
                else:   
                    meter.is_issued = True
                    meter.contractor = Contractor.objects.get(id=data.get('contractor'))

                meter.save()
                success_response['message'] = "Meter Updated Successfully"

            elif module == 'issue_def_qty':
                updated = 0
                created = 0


                # for meterial in InventoryMaterial.objects.filter(is_issue=True,auto_issue=True):
                    
                #     issue_qty = meterial.issue_qty
                #     MaterialOrderItem.objects.filter(material=meterial).update(
                #         quantity=issue_qty,
                #         rate=meterial.value,
                #         amount=issue_qty*meterial.value
                #     )
                #     updated += 1

                #     mt = meterial

                #     print (mt.name, mt.issue_qty, '\n')

                if True:


                    for service in ServiceOrder.objects.all():
                        service_type = service.service_type
                        meter_no = service.new_meter
                        meter = Meter.objects.get(meter_no=meter_no)

                        phase = meter.linked_phase
                        # get linked materials
                        pk = data.get('pk', '*')
                        if pk == '*':
                            material = ServiceMaterials.objects.filter(service=service_type,phase=phase)
                        else:
                            item = InventoryMaterial.objects.get(pk=pk)
                            material =ServiceMaterials.objects.filter(service=service_type,material=item,phase=phase)
                        for mt in material:
                            try:
                            # create
                                MaterialOrderItem.objects.create(
                                    material_type='is',
                                    material=mt.material,
                                    quantity=mt.qty,
                                    rate=mt.material.value,
                                    amount = mt.qty * mt.material.value ,
                                    service_order=service
                                )
                                print(mt.qty,'of',mt.material.name,'added to',service.new_meter)
                                created += 1
                            except Exception as e:
                                print("NO NEED")

                success_response['message'] = f"UPDATED {updated}, CREATED:{created}"

            elif module == 'update_retired_owner':
                start_date = data.get('start_date')
                end_date = data.get('end_date')
                all_ct = RetiredMetersTransactions.objects.filter(date_removed__in_range[start_date,end_date]).count()
                rr = 1
                for rt in RetiredMetersTransactions.objects.all():
                    spn = rt.spn
                    rrm = f"{rr} / {all_ct}"
                    try:
                        service = ServiceOrder.objects.get(spn=spn)
                        rt.foc = service.contractor
                        rt.save()
                        print(rrm,rt.box.box_no,"-",rt.sn,"Updated")

                    except Exception as e:
                        print(rrm,rt.box.box_no, "-", rt.sn, "Err: ",str(e))
                    rr += 1

                success_response['message'] = "Retired Records Updated Successfully"

            elif module == 'post_invoice':
                entry_no = data.get('entry_no')
                invoice = InvoiceHD.objects.get(entry_no=entry_no)
                regs = 0
                reg_amt = 0

                reps = 0
                rep_amt = 0

                news = 0
                new_amt = 0

                

                for tran in invoice.transactions():
                    meter_no = tran.get('asset')
                    remarks = tran.get('remarks')

                    srv = ServiceOrder.objects.get(new_meter=meter_no)

                    tm = srv.total_amount()
                    

                    if remarks == 'Installation':
                        news += 1
                        new_amt += tm
                    
                    if remarks == 'Replacement':
                        reps += 1
                        rep_amt += tm

                    if remarks == 'Regularization':
                        regs += 1
                        reg_amt += tm

                ps_entry_no = f"SSML-PS-{PaySlipHD.objects.all().conut()}"
                ref = entry_no
                entry_date = data.get('entry_date',timezone.now())
                ps_type = 'CI'
                remarks = f"Payslip for {regs + reps + news} jobs done ({regs} Regularization, {reps} Replacements, {news} New Installations)"
                total_amount = reg_amt + rep_amt + new_amt


                from datetime import datetime, timedelta

                # Ensure entry_date is a date object
                if isinstance(entry_date, str):
                    entry_date_obj = datetime.strptime(entry_date, "%Y-%m-%d").date()
                else:
                    entry_date_obj = entry_date

                due_date = entry_date_obj + timedelta(days=60)
                created_by = User.objects.get(pk=data.get('mypk'))

                print("Regularization",regs,reg_amt)
                print("Replacement",reps,rep_amt)
                print("Installations",news,new_amt)

                # create header
                PaySlipHD.objects.create(
                    entry_no=ps_entry_no,
                    etry_date=entry_date,
                    ps_type=ps_type,
                    ref=entry_no,
                    remarks=remarks,
                    
                )

                print(reg_amt + rep_amt + new_amt)

            elif module == 'post_grn':
                grn_id = data.get('id')
                grn = Grn.objects.get(id=grn_id)
                mypk = data.get('mypk')
                user = User.objects.get(id=mypk)
                try:
                    transactions = GrnTransaction.objects.filter(grn=grn)
                    for transaction in transactions:
                        
                        Cardex.objects.create(
                            doc_type='GR',
                            doc_no=grn.grn_no,
                            ref_no=grn.id,
                            material=transaction.material,
                            qty=transaction.total_qty,
                            location=grn.location,
                            created_at=grn.grn_date,
                        )
                    
                    grn.is_posted = True
                    grn.posted_by = user
                    success_response['message'] = "GRN Posted Successfully"
                except Exception as e:
                    Cardex.objects.filter(doc_no=grn.grn_no,doc_type='GR').delete()

                    grn.is_posted = False
                    success_response['status_code'] = 400
                    success_response['message'] = f"Error on line {sys.exc_info()[2].tb_lineno}: {e}"
                finally:
                    grn.save()
            elif module == 'grn':
                grn_id = data.get('id')
                grn = Grn.objects.get(id=grn_id)
                grn.supplier = Supplier.objects.get(id=data.get('supplier'))
                grn.grn_no = data.get('grn_no')
                grn.grn_date = data.get('grn_date')
                grn.remarks = data.get('remarks')
                grn.grn_type = data.get('grn_type')

                transactions = GrnTransaction.objects.filter(grn=grn)
                transactions.delete()
                for transaction in data.get('transactions'):
                    material = InventoryMaterial.objects.get(barcode=transaction.get('barcode'))
                    GrnTransaction.objects.create(
                            grn=grn, 
                            material=material, 
                            barcode=transaction.get('barcode'),
                            name=transaction.get('name'),
                            amount=transaction.get('amount'),
                            pack_qty=transaction.get('pack_qty'),
                            uom=transaction.get('uom'),
                            rate=transaction.get('rate'),
                            qty=transaction.get('qty'),
                            total_qty=Decimal(transaction.get('qty')) * Decimal(transaction.get('pack_qty'))    
                        )
                
                success_response['message'] = "GRN Updated Successfully"

            elif module == 'post_transfer':
                entry_no = data.get('entry_no','*')
                
                transfers = TransferHd.objects.filter(is_valid=True,is_posted=False,is_sent=True,entry_no=entry_no)

                # update recieved quantity
                for tran in data.get('trans'):
                    tran_id = tran.get('id')
                    tranx = TransferTr.objects.get(id=tran_id)
                    tranx.received_qty = tran.get('received_qty')
                    tranx.save()

                # make cardex
                for tr in transfers:
                    loc_from = tr.loc_fr
                    loc_to = tr.loc_to
                    entry_date = tr.entry_date

                    for tran in tr.transactions():
                        print(tran)
                        material_id = tran.get('material_id')
                        print(material_id)
                        material = InventoryMaterial.objects.get(id=material_id)
                        total = Decimal(tran.get('received_qty') ) * Decimal(tran.get('pack_qty'))

                        Cardex.objects.create(
                            doc_type='TRF',
                            doc_no = tr.entry_no,
                            ref_no = tr.entry_no,
                            material=material,
                            qty=total,
                            created_at=entry_date,
                            location=loc_to,
                        )

                        Cardex.objects.create(
                            doc_type='TRF',
                            doc_no = tr.entry_no,
                            ref_no = tr.entry_no,
                            material=material,
                            qty=total * Decimal(-1),
                            created_at=entry_date,
                            location=loc_from,
                        )
                    tr.is_posted = True
                    tr.save()

            elif module == 'unpost_transfer':
                entry_no = data.get('entry_no','*')
                if entry_no == '*':
                    transfers = TransferHd.objects.filter(is_valid=True,is_posted=True,is_sent=True)
                else:
                    transfers = TransferHd.objects.filter(is_valid=True,is_posted=True,is_sent=True,entry_no=entry_no)

                for tr in transfers:
                    entry = tr.entry_no

                    # delete from cardex
                    Cardex.objects.filter(
                        doc_type='TRF',
                        doc_no=entry
                    ).delete()

                    tr.is_posted = False
                    tr.save()

                response = success_response

            elif module == 'issue':
                issue_id = data.get('id')
                issue = Issue.objects.get(id=issue_id)
                issue.contractor = Contractor.objects.get(id=data.get('contractor'))
                issue.issue_date = data.get('issue_date')
                issue.remarks = data.get('remarks')
                issue.issue_type = data.get('issue_type')
                issue.car_no = data.get('car_no')
                issue.modified_by = User.objects.get(id=data.get('created_by'))

                transactions = IssueTransaction.objects.filter(issue=issue)
                transactions.delete()
                for transaction in data.get('transactions'):
                    material = InventoryMaterial.objects.get(barcode=transaction.get('barcode'))
                    IssueTransaction.objects.create(
                        issue=issue,
                        material=material,
                        qty=transaction.get('qty'),
                        pack_qty=transaction.get('pack_qty'),
                        uom=transaction.get('uom'),
                        rate=transaction.get('rate'),
                        barcode=transaction.get('barcode'),
                        name=transaction.get('name'),
                        total_qty=Decimal(transaction.get('qty')) * Decimal(transaction.get('pack_qty')),
                        amount=Decimal(transaction.get('qty')) * Decimal(transaction.get('rate'))
                    )
                issue.save()
                success_response['message'] = "Issue Updated Successfully"

            elif module == 'post_issue':
                
                try:
                    print(data)
                    issue_id = data.get('id','*')
                    if issue_id == '*':
                        issues = Issue.objects.filter(is_posted=False)
                    else:
                        issues = Issue.objects.filter(id=issue_id)
                    for issue in issues:
                        tp = issue.issue_type
                        mypk = data.get('mypk')
                        ct = 0

                        foc_id = issue.contractor
                        contractor = Contractor.objects.get(id=mypk)
                        foc_email = contractor.email
                        foc_phone = contractor.phone



                        user = User.objects.get(id=mypk)
                        transactions = IssueTransaction.objects.filter(issue=issue)
                        
                        for transaction in transactions:
                            location = transaction.issue.location
                            ct += 1
                            qty = transaction.total_qty * -1
                            if tp == 'RET':
                                qty = transaction.total_qty
                            
                            if tp == 'ISS':
                                qty = qty

                            if tp == 'CIS':
                                qty = qty

                            Cardex.objects.create(
                                doc_type=tp,
                                doc_no=issue.issue_no,
                                ref_no=issue.id,
                                material=transaction.material,
                                qty=qty,
                                created_at=issue.issue_date,
                                location=location
                            )
                            issue.is_posted = True
                            issue.posted_by = user
                            issue.save()
                    success_response['message'] = f"Issue Posted Successfully {ct}"
                except Exception as e:
                    Cardex.objects.filter(doc_no=issue.issue_no,doc_type='IS').delete()
                    raise Exception(e)

                issue.save()
            elif module == 'unpost_issue':
                ct = 0
                issue_id = data.get('id','*')
                if issue_id == '*':
                    issues = Issue.objects.filter(is_posted=True)
                else:
                    issues = Issue.objects.filter(id=issue_id)
                
                for issue in issues:
                    ct += 1
                    issue.is_posted = False
                    issue.posted_by = None
                    Cardex.objects.filter(doc_no=issue.issue_no, doc_type__in=['ISS', 'RET']).delete()
                    issue.save()
                success_response['message'] = f"Issue Unposted Successfully {ct}"


            elif module == 'unpost_grn':
                grn_id = data.get('id')
                grn = Grn.objects.get(id=grn_id)
                grn.is_posted = False
                grn.posted_by = None
                grn.save()
                Cardex.objects.filter(doc_no=grn.grn_no,doc_type='GR').delete()
                success_response['message'] = "GRN Unposted Successfully"

                

            elif module == 'service':
                id = data.get('id')
                name = data.get('service_name')
                description = data.get('service_description')
                uom = data.get('service_uom')
                rate = data.get('service_rate')

                service = Service.objects.get(id=id)
                service.name = name
                service.description = description
                service.uom = uom
                service.rate = rate
                service.save()
                success_response['message'] = "Service Updated Successfully"
            elif module == 'service_order_item':
                
                service_order_item = ServiceOrderItem.objects.get(id=data.get('service_item_id'))
                service_order_item.quantity = data.get('serv_qty')
                user = User.objects.get(id=data.get('mypk'))
                service_order_item.modified_by = user
                service_order_item.amount = Decimal(data.get('serv_qty')) * Decimal(service_order_item.rate)
                service_order_item.save()
                success_response['message'] = "Service Order Item Updated Successfully"

            elif module == 'contractor':
                print(data)
                id = data.get('id')
                contractor = Contractor.objects.get(id=id)


                # contractor.link = data.get('link')
                # contractor.owner = data.get('owner_name')
                # contractor.company = data.get('company')
                # contractor.gh_card_no = data.get('ghana_card')

                contractor.owner_phone = data.get('owner_phone')
                contractor.owner_email = data.get('owner_email')
                # contractor.comp_reg_number = data.get('comp_reg_number')
                # contractor.business_type = data.get('business_type')
                # contractor.region = data.get('region')
                # contractor.gh_post = data.get('gh_post')
                # contractor.business_address = data.get('business_address')

                contractor.phone = data.get('business_phone_number')
                contractor.email = data.get('business_email')

                # contractor.city = data.get('city')
                # contractor.postal_code = data.get('gh_post')
                # contractor.gh_post_code = data.get('gh_post')
                # contractor.is_installer = data.get('is_installer', True)
                # contractor.bank_name = data.get('bank_name')
                # contractor.bank_acct_number = data.get('bank_acct_number')
                # contractor.bank_branch = data.get('bank_branch')
                # debit = data.get('debit')
                # debit_ledger = Ledger.objects.get(pk=debit)
                # contractor.debit_ledger = debit_ledger

                contractor.save()

                foc = Contractor.objects.get(id=id)
                link = shorten_url(f"{BASE_URL}ssml/foc-portal/my-company/")

                # Email template
                email_template = f"""
                <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                    <h2 style="color: #FF8C00;">Profile Verified: Welcome to FOC NODE</h2>

                    <p>Dear {foc.owner},</p>

                    <p>Your contractor profile has been successfully updated and verified in the SSML Cloud ERP system.</p>

                    <p><strong>System Access Granted:</strong> You now have full access to <strong>FOC NODE</strong>, our comprehensive enterprise solution for managing electricity smart meter installations, inventory tracking, financial billing, and contractor compliance.</p>

                    <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #FF8C00; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #333; font-size: 16px;">Training & Guides</h3>
                        <p style="margin-bottom: 10px; font-size: 14px;">Before you begin, please review our training materials to understand how to navigate the system and process your claims:</p>
                        <ul style="margin-bottom: 0; padding-left: 20px; line-height: 1.6; font-size: 14px;">
                            <li><strong>Video Tutorials:</strong> <a href="https://ocean.rootechits.com/stream/series/27ODXPfa1mkA" style="color: #FF8C00; font-weight: bold; text-decoration: none;">Watch Step-by-Step Videos</a></li>
                            <li><strong>Written Guide:</strong> <a href="https://rootechits.com/blog.php?uni=sneda-foc-node-app" style="color: #FF8C00; font-weight: bold; text-decoration: none;">Read the Official Blog Manual</a></li>
                        </ul>
                    </div>

                    <h3 style="color: #333; font-size: 16px; margin-top: 25px;">Quick Access & App Downloads</h3>
                    <p>You can manage your operations directly from your browser, or install our dedicated applications for Android and Windows.</p>

                    <table width="100%" cellspacing="0" cellpadding="0" style="margin: 20px 0;">
                        <tr>
                            <td align="center" style="padding-bottom: 12px;">
                                <a href="https://focnode.rootechits.com/" style="background-color: #333333; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; width: 250px;">Open Web Dashboard</a>
                            </td>
                        </tr>
                        <tr>
                            <td align="center" style="padding-bottom: 12px;">
                                <a href="https://ocean.rootechits.com/static/uploads/appversion/app-release.apk" style="background-color: #FF8C00; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; width: 250px;">Download Android App</a>
                            </td>
                        </tr>
                        <tr>
                            <td align="center">
                                <a href="https://ocean.rootechits.com/static/uploads/apps/2026-04-29_18-01-17/Release.zip" style="background-color: #005A9C; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; width: 250px;">Download Windows App</a>
                            </td>
                        </tr>
                    </table>

                    <p style="font-size: 13px; color: #555; text-align: center;"><em>*For the best mobile experience, Android users should install the APK. Windows users can extract and run the desktop Release.zip file.</em></p>

                    <p>If you experience any issues accessing the web dashboard, installing the applications, or viewing your invoices, please reach out to Felix or Raymond for immediate technical support.</p>

                    <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">

                    <p style="font-size: 14px; color: #666;">
                        Best regards,<br>
                        <strong>System Administration | FOC NODE</strong><br>
                        <span style="font-size: 12px; color: #999;">Powered by RITS & Sneda SML Team</span>
                    </p>
                </div>
                """

                # SMS template
                sms_template = f"Dear {foc.owner}, your profile is now verified! Please check your email ({foc.email}) for your FOC NODE app download and login instructions."

                # Send notifications
                if contractor.email:
                    MailQueues.objects.create(
                        sender=MailSenders.objects.get(is_default=True),
                        recipient=data.get('owner_email'),
                        subject="Sneda SML Contractor Account Update",
                        body=email_template,
                        mail_key=make_md5_hash(f"contractor_update_{contractor.id}")
                    )

                if foc.phone:
                    to = foc.phone.replace('233', '0').replace('+233', '0')
                    if len(to) == 10:
                        Sms.objects.create(
                            api=SmsApi.objects.get(is_default=True),
                            to=to,
                            message=sms_template
                        )


            elif module == 'service_order_return':
                id = data.get('ret_id')
                return_item = ServiceOrderReturns.objects.get(id=id)
                return_item.quantity = data.get('ret_qty')
                return_item.modified_by = User.objects.get(id=data.get('mypk'))
                return_item.save()
                success_response['message'] = "Service Order Return Updated Successfully"
              
            elif module == 'close_service_order':
                id = data.get('id')
                mypk = data.get('mypk')
                user = User.objects.get(id=mypk)
                service_order = ServiceOrder.objects.get(id=id)
                total_amount = service_order.total_amount()
                print(total_amount)

                try:


                    Ledger.objects.create(
                        contractor=service_order.contractor,
                        amount=total_amount,
                        reference_no=service_order.new_meter,
                        transaction_type='credit',
                        remarks=f"Service Order {service_order.id} Closed",
                        created_by=user
                    )

                except Exception as e:
                    pass

                service_order.status = 'completed'
                service_order.closed_by = user
                service_order.total_amount = total_amount
                contractor_id = service_order.contractor.id
                service_order.save()
                success_response['message'] = contractor_id

            elif module == 'ret_def_rec':
                try:
                    service_id = data.get('service_id')
                    service = ServiceOrder.objects.get(id=service_id)
                    user = User.objects.get(pk=data.get('mypk'))
                    for service in ServiceOrder.objects.all():
                        for material in InventoryMaterial.objects.filter(is_return=True):
                            try:
                                ServiceOrderReturns.objects.create(
                                service_order=service,
                                material=material,
                                quantity=1,
                                created_by=user
                            )
                            except Exception as e:
                                print("Error")
                                print(e)
                                pass
                    success_response['status_code'] = 200
                    success_response['message'] = 'done'
                except Exception as e:
                    success_response['status_code'] = 505
                    success_response['message'] = str(e)

                print(success_response)

            elif module == "service_type":
                debit_account = data.get('debit_account')
                credit_account = data.get('credit_account')
                service_id = data.get('service_id')

                try:
                    service_type = ServiceType.objects.get(pk=service_id)
                    service_type.debit_account_id = debit_account
                    service_type.credit_account_id = credit_account
                    service_type.save()
                    success_response['status_code'] = 200
                    success_response['message'] = "Service type updated successfully"
                except ServiceType.DoesNotExist:
                    success_response['status_code'] = 404
                    success_response['message'] = "Service type not found"
                except Exception as e:
                    success_response['status_code'] = 500
                    success_response['message'] = str(e)
                
            
        
        
            elif module == 'invoice_update':
                try:
                    invoice_id = data.get('invoice_id')
                    invoice = InvoiceHD.objects.get(id=invoice_id)
                    
                    if invoice.is_posted:
                        raise Exception("Cannot update a posted invoice")
                        
                    contractor_id = data.get('contractor')
                    invoice.contractor = Contractor.objects.get(id=contractor_id)
                    invoice.entry_date = data.get('entry_date')
                    invoice.remarks = data.get('remarks')
                    
                    transactions = data.get('transactions')
                    
                    # Delete old transactions
                    InvoiceTransactions.objects.filter(entry=invoice).delete()
                    
                    total = 0
                    for transaction in transactions:
                        InvoiceTransactions(
                            entry=invoice,
                            service_date=transaction.get('date') or transaction.get('service_date'),
                            asset=transaction.get('meter') or transaction.get('asset'),
                            amount=transaction.get('amount'),
                            remarks=transaction.get('service') or transaction.get('remarks')
                        ).save()
                        total += Decimal(str(transaction.get('amount')))
                    
                    invoice.total_amount = total
                    invoice.save()
                    
                    success_response['message'] = "Invoice Updated Successfully"
                except Exception as e:
                    success_response['status_code'] = 400
                    success_response['message'] = f"Update Error: {e}"
            
            elif module == 'flat_for_invoice':
                meter_numbers = json.loads(data)
                print(meter_numbers)
                for meter_data in meter_numbers:
                    service_date = meter_data.get('service_date')
                    meter_no = meter_data.get('meter_no')

                    print(meter_no,service_date)
                    ## update flag in service

                    service =ServiceOrder.objects.filter(
                        new_meter=meter_no
                    ).last()

                    if service:

                        print(f"Meter {meter_no}- {service_date} flagged for invoice")
                        service.flag_for_invoice = True
                        service.ecg_date = service_date
                        service.save()
                    else:
                        print(f"Service does not exist {service_date}")
                    print()


                success_response['message'] = "Meters Flagged for Invoice"
                success_response['status_code'] = 200
                

            elif module == 'approve_ecg_invoice':
                try:
                    invoice_id = data.get('id')
                    invoice = EcgInvoiceHd.objects.get(id=invoice_id)
                    invoice.is_approved = True
                    invoice.approved_by = User.objects.get(pk=data.get('mypk'))
                    invoice.save()
                    success_response['message'] = "ECG Invoice Approved Successfully"
                except Exception as e:
                    success_response['status_code'] = 400
                    success_response['message'] = f"Approval Error: {e}"

            elif module == 'post_ecg_invoice':
                try:
                    invoice_id = data.get('id')
                    invoice = EcgInvoiceHd.objects.get(id=invoice_id)
                    if not invoice.is_approved:
                        raise Exception("Invoice must be approved before posting")
                    invoice.is_posted = True
                    invoice.save()
                    success_response['message'] = "ECG Invoice Posted Successfully"
                except Exception as e:
                    success_response['status_code'] = 400
                    success_response['message'] = f"Posting Error: {e}"
            else:
                success_response['status_code'] = 505
                success_response['message'] = "Invalid Module for PATCH"
        
        else:
            success_response['status_code'] = 400
            success_response['message'] = f"Method Not Found"

        response = success_response

    except Exception as e:
        error_type, error_instance, traceback = sys.exc_info()
        tb_path = traceback.tb_frame.f_code.co_filename
        line_number = traceback.tb_lineno
        response["status_code"] = 500
        response[
            "message"] = f"An error occurred on line {line_number} in file {tb_path}. Details: {e}"

    return JsonResponse(response, safe=False)










