import json
import sys

import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout, get_user_model
from django.contrib.auth.models import User, Permission
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from admin_panel.anton import md5only, remove_html_tags, generate_random_password, make_md5_hash, generate_api_key
from admin_panel.cron_exe import execute_script
from admin_panel.models import BankAccounts, DocApprovals, GeoCity, GeoCitySub, Reminder, SmsApi, UserAddOns, EvatCredentials, \
    Locations, \
    Departments, TicketTrans, Sms, TicketHd, MailSenders, MailQueues, MailAttachments, BusinessEntityTypes
from blog.anton import make_md5
from ocean.settings import RET_DB_HOST, RET_DB_USER, RET_DB_PASS, RET_DB_NAME, REST_DB_NAME
from reports.models import DepartmentReportMailQue
from retail.db import ret_cursor
from retail.models import ProductSupplier, ProductGroup, ProductSubGroup, Products
from servicing.models import ServiceCard
from taskmanager.models import Tasks, TaskTransactions
from .models import Company


@csrf_exempt
def index(request):
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
        from django.contrib.auth.models import User
        if method == 'PUT':  # write
            if module == 'geo':  # geographical condition
                part = data.get('part')

                if part == 'city' or part == 'region':  # add city
                    name = data.get('name')
                    us_pk = data.get('owner')

                    GeoCity(name=name, owner=User.objects.get(pk=us_pk)).save()
                    response = success_response
                elif part == 'sub':
                    city = data.get('city')
                    name = data.get('name')
                    us_pk = data.get('owner')

                    GeoCitySub(name=name, owner=User.objects.get(pk=us_pk), city=GeoCity.objects.get(pk=city)).save()
                    response = success_response

            elif module == 'company':
                company = Company.objects.create(
                    name= data.get('companyName', ''),
                    address= data.get('companyAddress', ''),
                    email=data.get('companyEmail', ''),
                    phone= data.get('companyPhone', ''),
                )
                response = success_response.copy()

            elif module == 'sync_inventory':

                enityt_pk = data.get('enityt_pk')
                entity = BusinessEntityTypes.objects.get(pk=enityt_pk)
                e_type = entity.entity_type_name.lower()
                print(e_type)
                db_config = {}
                if e_type == 'retail':

                    db_config['host'] = RET_DB_HOST
                    db_config['user'] = RET_DB_USER
                    db_config['password'] = RET_DB_PASS
                    db_config['db'] = RET_DB_NAME

                    supplier_query = "select supp_code as 'code',supp_name as 'name',contact as 'person',phone1 as 'phone',address1 as 'email',address2 as 'city',country_id as 'country' from supplier"
                    group_query = f"select group_code,group_des from group_mast"
                    sub_group_query = f"SELECT group_code,(select group_des from group_mast where group_code = sub_group.group_code) as 'group', sub_group,sub_group_des from sub_group"
                    products_query = "SELECT item_code, barcode, item_des, (SELECT group_des FROM group_mast WHERE group_mast.group_code = prod_mast.group_code) AS 'group', (SELECT sub_group_des FROM sub_group WHERE sub_group.group_code = prod_mast.group_code AND sub_group.sub_group = prod_mast.sub_group) AS 'sub_group', (SELECT supp_name FROM supplier WHERE supplier.supp_code = prod_mast.supp_code) AS 'supplier', retail1 FROM prod_mast WHERE item_type != 0"


                elif e_type == 'restaurant':
                    db_config['host'] = RET_DB_HOST
                    db_config['user'] = RET_DB_USER
                    db_config['password'] = RET_DB_PASS
                    db_config['db'] = REST_DB_NAME

                    supplier_query = "select supp_code as 'code',supp_name as 'name',contact as 'person',phone1 as 'phone',address1 as 'email',address2 as 'city',country_id as 'country' from supplier"
                    group_query = f"select group_code,group_des from group_mast"
                    sub_group_query = f"SELECT group_code,(select group_des from group_mast where group_code = sub_group.group_code) as 'group', sub_group,sub_group_des from sub_group"
                    products_query = "SELECT item_code, barcode, item_des, (SELECT group_des FROM group_mast WHERE group_mast.group_code = prod_mast.group_code) AS 'group', (SELECT sub_group_des FROM sub_group WHERE sub_group.group_code = prod_mast.group_code AND sub_group.sub_group = prod_mast.sub_group) AS 'sub_group', (SELECT supp_name FROM supplier WHERE supplier.supp_code = prod_mast.supp_code) AS 'supplier', (select top 1 retail from price_lev where price_group = '201' and item_code = prod_mast.item_code) as 'retail' FROM prod_mast WHERE item_type = 5"
                    print(products_query)


                else:
                    raise Exception("Invalid Entity Type")

                    # sync suppliers

                conn = ret_cursor(db_config['host'], '', db_config['db'], db_config['user'], db_config['password'])
                cursor = conn.cursor()
                cursor.execute(supplier_query)
                counts = 0
                not_counted = 0
                mk = 1
                fetch = cursor.fetchall()
                mklen = len(fetch)
                for supplier in fetch:
                        print(f"Supplier {mk} / {mklen}")
                        code = supplier[0].strip()
                        name = supplier[1].strip()
                        person = supplier[2].strip() if supplier[2] is not None else supplier[2]
                        phone = '' if supplier[3] is None else supplier[3].strip()
                        email = '' if supplier[4] is None else supplier[4].strip()
                        city = '' if supplier[5] is None else supplier[5].strip()
                        country = '' if supplier[6] is None else supplier[6].strip()

                        try:
                            if ProductSupplier.objects.filter(code=code,entity=entity).exists():
                                ProductSupplier.objects.filter(code=code).update( name=name, phone=phone,
                                                                      person=person,
                                                                      email=email, city=city,
                                                                      country=country,entity=entity)
                            else:
                                ProductSupplier.objects.create(code=code, name=name, phone=phone,
                                                                                 person=person,
                                                                                 email=email, city=city,
                                                                                 country=country,entity=entity)
                            counts = counts + 1
                        except Exception as e:
                            not_counted = not_counted + 1

                        mk += 1

                    # sync groups

                # groups
                mk = 1


                cursor.execute(group_query)
                count = 0
                not_counted = 0
                fetch = False
                fetch = cursor.fetchall()
                mklen = len(fetch)
                for group in fetch:
                        print(f"Group {mk} / {mklen}")
                        mk += 1
                        code, name = group[0].strip(), group[1].strip()
                        try:
                            if ProductGroup.objects.filter(code=code,entity=entity).exists():
                                # update
                                ProductGroup.objects.filter(code=code).update(name=name,entity=entity)
                            else:
                                get, add = ProductGroup.objects.get_or_create(code=code, name=name,entity=entity)
                            count = count + 1
                        except Exception as e:
                            not_counted = not_counted + 1

                    # sync sub groups

                # sub group

                cursor.execute(sub_group_query)
                count = 0
                not_counted = 0
                errors = []
                fetch = False
                fetch = cursor.fetchall()
                mklen = len(fetch)

                for sub_group in fetch:
                        print(f"Subgroup {mk} / {mklen}")
                        mk += 1
                        group_code, group_des, sub_group_code, sub_group_des = sub_group[0], sub_group[1].strip(), \
                            sub_group[2].strip(), sub_group[3].strip()

                        print(sub_group)
                        group, add = ProductGroup.objects.get_or_create(code=group_code, name=group_des,entity=entity)

                        if add:
                            group = ProductGroup.objects.get(code=group_code, name=group_des,entity=entity)

                        try:
                            if ProductSubGroup.objects.filter(group=group,entity=entity).exists():
                                ProductSubGroup.objects.filter(group=group, code=sub_group_code).update(
                                                                      name=sub_group_des,entity=entity)
                            else:
                                sub, create = ProductSubGroup.objects.get_or_create(group=group, code=sub_group_code,
                                                                                name=sub_group_des,entity=entity)
                            count = count + 1
                        except Exception as e:
                            errors.append(e)
                            not_counted = not_counted + 1

                    # sync products


                # products
                print(products_query)
                cursor.execute(products_query)
                saved = 0
                not_synced = 0
                error = []
                mk = 1
                fetch = cursor.fetchall()
                mklen = len(fetch)
                print(mklen)
                for product in fetch:
                        print(f"Product {mk} / {mklen}")
                        mk += 1
                        code = product[0]
                        barcode = str(product[1]).strip()
                        item_des = product[2].strip()
                        group = product[3]
                        # print(product[4])
                        try:
                            sub_group = product[4].strip()
                        except Exception as e:
                            sub_group = product[4]

                        supplier = product[5]
                        retail1 = product[6] if product[6] is not None else 0
                        print(retail1)

                        # add to products
                        subgroup = ProductSubGroup.objects.get(code='999')
                        if ProductSubGroup.objects.filter(code=sub_group,entity=entity).count() == 1:
                            subgroup = ProductSubGroup.objects.get(name=sub_group,entity=entity)
                            # delete product
                        if Products.objects.filter(code=code,entity=entity).exists():
                            # update
                            prod = Products.objects.get(code=code,entity=entity)
                            prod.barcode = barcode
                            prod.name = item_des
                            prod.price = retail1
                            prod.subgroup = subgroup
                            prod.entity = entity
                            prod.save()
                        else:
                            # save new
                            Products.objects.get_or_create(subgroup=subgroup, name=item_des, barcode=barcode,
                                                           code=code, price=retail1,entity=entity)
                            saved = saved + 1
                        # else:
                        #     not_synced = not_synced + 1
                        #     error.append(f"{barcode} - {item_des} # sub group {sub_group} / does not exist")

                conn.close()


            elif module == 'set_loc_manager':
                mana_pk = data.get('manager')
                set_by_pk = data.get('mypk')
                loc_pk = data.get('loc_pk')

                manager = UserAddOns.objects.get(pk=mana_pk)
                set_by_pk = User.objects.get(pk=set_by_pk)
                location = Locations.objects.get(pk=loc_pk)

                location.manager = manager
                location.save()

                response= success_response

            elif module == 'tools':
                task = data.get('task')
                if task == 'set_message':
                    msg = data.get('message')
                    messages.success(request, msg)

                elif task == 'check_reminders':
                    reminders = Reminder.objects.filter(status=1).order_by('rem_date', 'rem_time')
                    for reminder in reminders:
                        rem_time = reminder.rem_time
                        rem_date = reminder.rem_date
                        owner = reminder.owner

                        add_on = UserAddOns.objects.get(user=owner)

                        from datetime import datetime

                        # Assuming 'rem_time' is a time object and 'rem_date' is a date object
                        rem_datetime = datetime.combine(rem_date, rem_time)

                        # Get current date and time
                        current_datetime = datetime.now()
                        sent = 0
                        not_sent = 0
                        # Compare
                        if rem_datetime <= current_datetime:
                            # send

                            sms_api = SmsApi.objects.get(is_default=1)

                            phone = add_on.phone
                            message = f"Title : {reminder.title} \nDate : {reminder.rem_date} \nTime : {reminder.rem_time} \nDetails : {reminder.message}"
                            Sms.objects.create(
                                api=sms_api,
                                to=phone,
                                message=message,
                            )




                            reminder.status = 99
                            reminder.save()

                        else:
                            # dont send
                            not_sent += 1

                        success_response['message'] = {
                            'sent': sent, 'pending': not_sent
                        }

                        response = success_response

            elif module == 'doc_app_auth':
                user_pk = data.get('user_pk')
                user = User.objects.get(pk=user_pk)
                doc_type = data.get('doc_type')
                DocApprovals(user=user, doc_type=doc_type).save()

                success_response['message'] = "Approver Added"
                response = success_response

            elif module == 'reminder':
                owner_pk = data.get('owner')
                title = data.get('title')
                message = data.get('message')
                date = data.get('date')
                time = data.get('time')

                Reminder(title=title, message=message, rem_date=date, rem_time=time,
                         owner=User.objects.get(pk=owner_pk)).save()
                success_response['message'] = "Reminder Scheduled"
                response = success_response

                # save reminder

            elif module == 'evat_credentials':
                server_ip = data.get('server_ip')
                server_location = data.get('server_location')
                company_tin = data.get('company_tin')
                company_name = data.get('company_name')
                company_security_key = data.get('company_security_key')
                owner = data.get('owner')

                creating_user = User.objects.get(pk=owner)
                inv_req = f"http://{server_ip}/EvatAPI/api/EvatRequest"
                z_rez = f"http://{server_ip}/EvatAPI/api/EvatZreport"

                EvatCredentials(server_ip=server_ip, server_location=server_location, company_tin=company_tin,
                                company_name=company_name, company_security_key=company_security_key,
                                owner=creating_user, z_rez=z_rez, inv_req=inv_req).save()

                success_response['message'] = "Credential Saved"
                response = success_response

                pass

            elif module == 'location':
                print(data)
                server_ip = data.get('server_ip')
                server_location = data.get('server_location')
                code = data.get('code')
                descr = data.get('descr')
                db_user = data.get('db_user')
                db_password = data.get('db_password')
                db = data.get('db')
                owner = data.get('owner')
                creating_user = User.objects.get(pk=owner)
                Locations(server_location=server_location, ip_address=server_ip, code=code, descr=descr,
                          db_user=db_user, db=db, db_password=db_password, owner=creating_user).save()

                success_response = "LOCATION SAVED"
                response = success_response

            elif module == 'ticketupdate':
                date_time = data.get('datetime')
                ticket = data.get('ticket')
                title = data.get('title')
                description = data.get('description')
                owner = data.get('mypk')
                notify = data.get('notify')

                if ServiceCard.objects.filter(ticket_id=ticket).count() == 1:
                    service = ServiceCard.objects.get(ticket_id=ticket)
                    task = service.task
                    TaskTransactions(task=task, title=title, description=description, owner_id=owner).save()

                TicketTrans(ticket_id=ticket, title=title, tran=description, user_id=owner, created_on=date_time).save()

                if notify == 'YES':
                    tickethd = TicketHd.objects.get(pk=ticket)
                    tick_owner = tickethd.owner
                    user_details = UserAddOns.objects.get(user=tick_owner)
                    Sms(to=user_details.phone, message=f"TICKET UPDATE\nTitle: {title}\nDescription: {description}",
                        api=SmsApi.objects.get(is_default=1)).save()

                success_response['message'] = "TIcket Updated"
                response = success_response

            elif module == 'mail_senders':
                host = data.get('host')
                port = data.get('port')
                address = data.get('address')
                password = data.get('password')
                is_default = data.get('is_default')
                is_tls = data.get('is_tls')
                owner = User.objects.get(pk=data['mypk'])

                MailSenders(host=host, port=port, address=address, password=password, is_default=is_default,
                            is_tls=is_tls, owner=owner).save()
                success_response['message'] = "Sender Added"
                response = success_response

            elif module == 'que_mail':
                print(data)
                sender_pk = data.get('sender') or 'default'
                if sender_pk != 'default':
                    sender = MailSenders.objects.get(pk=data.get('sender'))
                else:
                    sender = MailSenders.objects.get(is_default=True)
                recipient = data.get('recipient')
                subject = data.get('subject')
                body = data.get('body')
                cc = data.get('cc','')

                mail_key = make_md5(f"{timezone.now()}{subject}{recipient}{body}{sender.pk}{sender.address}")
                MailQueues(sender=sender, recipient=recipient, subject=subject, body=body, cc=cc,mail_key=mail_key).save()
                just_q = MailQueues.objects.get(mail_key=mail_key)

                trigger = data.get('trigger')
                ref = data.get('ref')
                if trigger == 'servicing':
                    queu_by = User.objects.get(pk=data.get('mypk'))
                    service = ServiceCard.objects.get(pk=ref)
                    docs = service.documents()
                    for doc in docs:
                        print(doc.doc_url)
                        MailAttachments(
                            mail=just_q,
                            attachment=doc.document,
                        ).save()

                    # update transaction
                    TicketTrans(
                        ticket_id=service.ticket_id,
                        title="Issue Escalated",
                        tran="Email has been sent to service provider",
                        user=queu_by,

                    ).save()

                success_response['message'] = "Mail Added To Que"
                response = success_response

            elif module == 'broadcast_mail':
                sender = MailSenders.objects.get(is_default=True)
                users = UserAddOns.objects.all()
                message = data.get('body')
                subject = data.get('subject')
                for u in users:
                    us = u.user
                    email = us.email
                    body = message.replace('%name%', f"{us.get_full_name()}")
                    MailQueues(sender=sender, recipient=email, subject=subject, body=body, cc='').save()

                success_response['message'] = "Mail Added To Broadcast"
                response = success_response

            elif module == 'entity_type':
                entity_type_name = data.get('entity_type_name')
                entity_type_descr = data.get('entity_type_descr')
                company_pk = data.get('company')

                company = Company.objects.get(pk=company_pk)
                exists = company.entites.filter(entity_type_name__iexact=entity_type_name).exists()

                if exists:
                    response['message'] = "Entity already exists for this company"
                    return JsonResponse(response)

                BusinessEntityTypes.objects.create(
                    entity_type_name = entity_type_name,
                    entity_type_descr = entity_type_descr,
                    company = Company.objects.get(pk=company_pk)
                )

                success_response['message'] = "Entity Type Created"
                response = success_response

            elif module == 'update_profile_pic':
                import base64 as _base64
                from django.core.files.base import ContentFile as _ContentFile
                pk = data.get('mypk')
                file_base64 = data.get('file_base64')
                file_name = data.get('file_name', 'profile.jpg')
                try:
                    addon = UserAddOns.objects.get(user__pk=pk)
                    fmt, imgstr = file_base64.split(';base64,') if ';base64,' in file_base64 else (None, file_base64)
                    decoded = _base64.b64decode(imgstr)
                    content_file = _ContentFile(decoded, name=file_name)
                    addon.profile_pic.save(file_name, content_file, save=True)
                    success_response['message'] = addon.profile_pic.url
                    response = success_response
                except Exception as e:
                    response['status_code'] = 500
                    response['message'] = str(e)

            elif module == 'upload_compliance':
                import base64
                from django.core.files.base import ContentFile
                from employee.models import EmployeeDocuments, Documents

                pk = data.get('mypk')
                compliance_type_id = data.get('compliance_type')
                remarks = data.get('remarks', '')
                file_base64 = data.get('file_base64')
                file_name = data.get('file_name', 'document.jpg')

                try:
                    user_obj = User.objects.get(pk=pk)
                    document_type = Documents.objects.get(pk=compliance_type_id)

                    format, imgstr = file_base64.split(';base64,') if ';base64,' in file_base64 else (None, file_base64)
                    decoded_file = base64.b64decode(imgstr)
                    content_file = ContentFile(decoded_file, name=file_name)

                    emp_doc, created = EmployeeDocuments.objects.update_or_create(
                        user=user_obj,
                        document=document_type,
                        defaults={
                            'remark': remarks,
                            'status': 'pending',
                            'file': content_file
                        }
                    )

                    success_response['message'] = "Compliance document uploaded successfully"
                    response = success_response
                except Exception as e:
                    response['status_code'] = 500
                    response['message'] = str(e)

            else:
                response['status_code'] = 503
                response['message'] = f"UNKNOWN MODULE ( METHOD : {method}, MODULE : {module} )"


        elif method == 'VIEW':  # read

            if module == 'geo':  # geographical condition
                part = data.get('part')

                if part == 'city' or part == 'region':  # add city
                    key = data.get('key','*')
                    cts = []
                    if key == '*':
                        cities = GeoCity.objects.all().order_by('name')
                    else:
                        from django.db.models import Q
                        cities = GeoCity.objects.filter(
                            Q(name__icontains=f"{key}") | Q(pk=f"{key}")).order_by('name')
                    for city in cities:
                        subj = []
                        for sub in city.subs():
                            subj.append({
                                'name': sub.name,
                                'pk': sub.pk
                            })
                        obj = {
                            'pk': city.pk,
                            'name': city.name,
                            'timestamp': city.timestamp(),
                            'subs': subj
                        }
                        cts.append(obj)

                    success_response['message'] = cts
                    response = success_response

            elif module == 'entity_type':
                # get all if data is empty
                if not data:
                    arr = []
                    for et in BusinessEntityTypes.objects.all():
                        arr.append({
                            'pk': et.pk,
                            'name': et.entity_type_name,
                            'descr': et.entity_type_descr,
                            'bolt_menu':et.bolt_menu(),
                            'company_name' : et.company.name ,
                            'company_pk' : et.company.pk
                        })

                    success_response['message'] = arr
                    response = success_response
                    # get specific entity type
                else:
                    pk = data.get('pk')
                    entity = BusinessEntityTypes.objects.get(id=pk)
                    arr = []
                    arr.append({
                            'pk': entity.pk,
                            'name': entity.entity_type_name,
                            'descr': entity.entity_type_descr,
                            'bolt_menu':entity.bolt_menu(),
                            'company_name' : entity.company.name ,
                            'company_pk' : entity.company.pk
                    })
                    success_response['message'] = arr
                    response = success_response

            elif module == "company":
                if not data:
                    companies = Company.objects.all()
                    arr = []
                    for company in companies:
                        arr.append({
                            'pk': company.pk,
                            'name': company.name,
                            'address': company.address,
                            'email': company.email,
                            'phone': company.phone,
                            # 'timestamp': company.timestamp(),
                            # 'entity_type': {
                            #     'pk': company.entity_type.pk if company.entity_type else None,
                            #     'name': company.entity_type.entity_type_name if company.entity_type else None
                            # }
                        })
                    success_response['message'] = arr
                    response = success_response
                else:
                    pk = data.get("pk")
                    company = Company.objects.get(id=pk)
                    success_response['message'] = {
                        'pk': company.pk,
                        'name': company.name,
                        'address': company.address,
                        'email': company.email,
                        'phone': company.phone,
                        # 'timestamp': company.timestamp(),
                        # 'entity_type': {
                        #     'pk': company.entity_type.pk if company.entity_type else None,
                        #     'name': company.entity_type.entity_type_name if company.entity_type else None
                        # }
                    }
                    response = success_response

            elif module == 'doc_app_auth':
                pin = data.get('pin')
                doc_type = data.get('doc_type')
                if UserAddOns.objects.filter(auth_pin=md5only(pin)).count() == 1:
                    # get user
                    us = UserAddOns.objects.get(auth_pin=md5only(pin))
                    # validate if user can auth
                    auth_user = us.user
                    if DocApprovals.objects.filter(user=auth_user, doc_type='sales_proforma').count() == 1:
                        success_response['status_code'] = 200
                        success_response['message'] = us.user.pk
                    else:
                        success_response['status_code'] = 505
                        success_response['message'] = "Permission Denied"
                else:
                    success_response['status_code'] = 404
                    success_response['message'] = f"Invalid User {md5only(1234)}"

                response = success_response

            elif module == 'reminder':
                key = data.get('key')
                owner = data.get('owner')
                status = data.get('status')
                reminder_user = User.objects.get(pk=owner)

                if key == '*':
                    reminders = Reminder.objects.filter(owner=reminder_user).order_by('rem_date', 'rem_time')
                elif key == 'status':
                    reminders = Reminder.objects.filter(owner=reminder_user, status=status)
                else:
                    reminders = Reminder.objects.filter(owner=reminder_user, pk=key)

                rem = []

                for reminder in reminders:
                    obj = {
                        'pk': reminder.pk,
                        'title': reminder.title,
                        'message': reminder.message,
                        'date': reminder.rem_date,
                        'time': reminder.rem_time,
                        'status': reminder.status,
                        'owner': {
                            'pk': reminder.owner.pk,
                            'username': reminder.owner.username,
                            'name': f"{reminder.owner.first_name} {reminder.owner.last_name}"
                        }

                    }

                    rem.append(obj)

                success_response['message'] = rem
                response = success_response

            elif module == 'evat_credentials':
                keys = EvatCredentials.objects.all()
                arr = []
                for key in keys:
                    arr.append({
                        'pk': key.pk,
                        'server_ip': key.server_ip,
                        'server_location': key.server_location,
                        'company_tin': key.company_tin,
                        'company_name': key.company_name,
                        'company_security_key': key.company_security_key,
                        'inv_req': key.inv_req,
                        'z_rez': key.z_rez,
                        'status': key.stat()
                    })

                success_response['message'] = arr
                response = success_response

            elif module == 'dept_report':
                # get all department
                import openpyxl
                workbook = openpyxl.Workbook()

                departments = Departments.objects.all()
                from datetime import datetime
                current_datetime = datetime.now()
                formatted_datetime = current_datetime.strftime("%Y_%m_%d_%H_%M_%S")
                day_only = current_datetime.strftime('%Y-%m-%d')

                for department in departments:
                    members = department.members()
                    head_email = department.email_of_head
                    files = []
                    for member in members:
                        sheet = workbook.active
                        sheet['A1'] = "TITLE"
                        #sheet['B1'] = "DESCRIPTION"
                        sheet['B1'] = "LAST TRANSACTION"
                        sheet['C1'] = "Transaction Time"
                        sheet['D1'] = "Status"
                        user = member.user

                        file_name1 = f"{user.first_name}_{user.last_name}_report_as_of_{formatted_datetime}.xlsx"

                        file_name = f"static/general/task-reports/{file_name1}"
                        # get tasks
                        user_tasks = Tasks.objects.filter(owner=member.user)
                        print(member.user.username, f"has {user_tasks.count()} tasks")
                        sheet_count = 2
                        updt = True
                        if user_tasks.count() > 0:
                            for task in user_tasks:
                                title = task.title
                                descr = remove_html_tags(task.description)
                                last_transaction_time = "NO TRANSACTION"
                                last_transaction = "NO TRANSACTION"

                                if task.transaction().count() > 0:
                                    transactions = task.transaction().last()
                                    if not transactions.reported:
                                        last_transaction = remove_html_tags(transactions.description)
                                        last_transaction_time = transactions.created_date
                                        transactions.reported = False
                                        updt = True

                                sheet[f"A{sheet_count}"] = title
                                # sheet[f'B{sheet_count}'] = descr
                                sheet[f'B{sheet_count}'] = last_transaction
                                sheet[f'C{sheet_count}'] = last_transaction_time
                                sheet[f"D{sheet_count}"] = task.text_status()

                                sheet_count += 1
                                # for transaction in transactions:
                                #     tran_title = transaction.title
                                #     tran_descr = transaction.description
                                #     date_time = f"{transaction.created_date} {transaction.created_time}"
                                #
                                #     sheet[f"A{sheet_count}"] = title
                                #     sheet[f"B{sheet_count}"] = tran_title
                                #     sheet[f"C{sheet_count}"] = tran_descr
                                #     sheet[f"D{sheet_count}"] = date_time
                                #     sheet[f"E{sheet_count}"] = "NOT KNOWN"
                                #
                                #     sheet_count += 1

                            workbook.save(file_name)
                            files.append(file_name)
                            if updt:
                                transactions.save()

                    if len(files) > 0:
                        print(department.name,"SENT")
                        MailQueues(
                            sender=MailSenders.objects.get(is_default=True),
                            recipient=department.email_of_head,
                            subject=f"{department.name} task report as of {day_only}",
                            body=f"Attached to this email is the departmental report for {department.name}"
                        ).save()

                        save_mail = MailQueues.objects.filter(
                            sender=MailSenders.objects.get(is_default=True),
                            recipient=department.email_of_head,
                            subject=f"{department.name} task report as of {day_only}",
                            body=f"Attached to this email is the departmental report for {department.name}",
                            is_sent=False
                        ).last()

                        for file in files:
                            print(file)
                            MailAttachments(mail=save_mail,attachment=file).save()
                        ##DepartmentReportMailQue(department=department, files=files).save()

            elif module == 'dashboard_reports':
                from datetime import datetime, date, timedelta
                from django.db.models import Count, Sum
                from django.contrib.auth.models import User

                # 1. SSML Landing Report
                try:
                    from ssml.models import ServiceOrder, InventoryMaterial
                    total_installs = ServiceOrder.objects.count()
                    today_installs = ServiceOrder.objects.filter(service_date=date.today()).count()

                    reorder_count = 0
                    for mat in InventoryMaterial.objects.filter(is_active=True, reorder_qty__gt=0):
                        if mat.stock() <= mat.reorder_qty:
                            reorder_count += 1

                    first_order = ServiceOrder.objects.order_by('service_date').first()
                    avg_per_day = 0.0
                    avg_per_month = 0.0
                    if first_order and total_installs > 0:
                        days_diff = (date.today() - first_order.service_date).days or 1
                        months_diff = (date.today().year - first_order.service_date.year) * 12 + (date.today().month - first_order.service_date.month) or 1
                        avg_per_day = round(total_installs / days_diff, 1)
                        avg_per_month = round(total_installs / months_diff, 1)

                    best_contractor = "N/A"
                    top_c = ServiceOrder.objects.values('contractor__company').annotate(tot=Count('id')).order_by('-tot').first()
                    if top_c:
                        best_contractor = top_c['contractor__company'] or "N/A"

                    total_billable = 0
                    for m in InventoryMaterial.objects.filter(is_billable=True, is_active=True):
                        total_billable += m.stock()
                    stock_est_days = round(total_billable / avg_per_day) if avg_per_day > 0 else 0

                    ssml_report = {
                        'total_installs': total_installs,
                        'today_installs': today_installs,
                        'reorder_count': reorder_count,
                        'avg_per_day': avg_per_day,
                        'avg_per_month': avg_per_month,
                        'best_contractor': best_contractor,
                        'stock_estimate_days': stock_est_days,
                    }
                except Exception as e:
                    ssml_report = {'error': str(e)}

                # 2. Logistics
                try:
                    from logistics.models import DeliveryRequest, VehicleFuelTopUp
                    today_dt = datetime.now()
                    week_start = today_dt.date() - timedelta(days=today_dt.weekday())
                    week_end = week_start + timedelta(days=6)

                    logistics_total = DeliveryRequest.objects.filter(request_date__date__range=[week_start, week_end]).count()
                    logistics_completed = DeliveryRequest.objects.filter(status='delivered', arrival_time__date__range=[week_start, week_end]).count()
                    logistics_pending = DeliveryRequest.objects.filter(status='pending').count()
                    logistics_in_transit = DeliveryRequest.objects.filter(status='in_transit').count()
                    logistics_fuel_amount = VehicleFuelTopUp.objects.filter(date__range=[week_start, week_end]).aggregate(total=Sum('amount'))['total'] or 0
                    logistics_fuel_litres = VehicleFuelTopUp.objects.filter(date__range=[week_start, week_end]).aggregate(total=Sum('litres'))['total'] or 0

                    logistics_report = {
                        'total_requests': logistics_total,
                        'completed': logistics_completed,
                        'pending': logistics_pending,
                        'in_transit': logistics_in_transit,
                        'fuel_amount': float(logistics_fuel_amount),
                        'fuel_litres': float(logistics_fuel_litres),
                    }
                except Exception as e:
                    logistics_report = {'error': str(e)}

                # 3. CRM LOGS
                try:
                    from crm.models import Logs
                    from datetime import date
                    today_date = date.today()

                    recent_crm = []
                    for l in Logs.objects.filter(created_date=today_date).order_by('-id'):
                        recent_crm.append({
                            'customer': l.customer,
                            'company': l.company,
                            'subject': l.subject,
                            'description': l.description,
                            'success': l.success,
                            'created_date': str(l.created_date)
                        })

                    crm_report = {
                        'recent': recent_crm,
                    }
                except Exception as e:
                    crm_report = {'error': str(e)}

                # 4. ATTENDANCE Summary in HRM (Biometric)
                try:
                    from iclock.models import Employee, RawAttendance
                    today_date = date.today()

                    active_employees = Employee.objects.filter(is_resigned=False)
                    raw_today = RawAttendance.objects.filter(day=today_date, employee__is_resigned=False).select_related('employee', 'employee__area')

                    late_count = 0
                    on_time_count = 0
                    for raw in raw_today:
                        is_late = False
                        if raw.employee and raw.employee.area and raw.employee.area.work_start_time:
                            if raw.first_punch > raw.employee.area.work_start_time:
                                is_late = True
                        if is_late:
                            late_count += 1
                        else:
                            on_time_count += 1

                    present_emp_ids = set(raw_today.values_list('employee_id', flat=True))
                    absent_count = active_employees.exclude(id__in=present_emp_ids).count()

                    hrm_report = {
                        'on_time': on_time_count,
                        'late': late_count,
                        'absent': absent_count,
                    }
                except Exception as e:
                    hrm_report = {'error': str(e)}

                # 5. CMMS
                try:
                    from cmms.models import StockCountHD, JobCard, ServiceFollowup
                    cmms_active_stock = StockCountHD.objects.filter(status=1).exists()
                    cmms_active_stock_name = StockCountHD.objects.filter(status=1).first().name if cmms_active_stock else "None"
                    cmms_pending_jobs = JobCard.objects.filter(is_ended=False).count()
                    cmms_followups = ServiceFollowup.objects.filter(is_completed=False).count()

                    cmms_report = {
                        'active_stock_count': cmms_active_stock,
                        'active_stock_name': cmms_active_stock_name,
                        'pending_jobs': cmms_pending_jobs,
                        'service_followups': cmms_followups,
                    }
                except Exception as e:
                    cmms_report = {'error': str(e)}

                # 6. Servicing Material Requests
                try:
                    from servicing.models import MR_Hd, MR_Trans
                    servicing_pending_materials = MR_Hd.objects.filter(is_approved=False).count()
                    servicing_materials = []
                    for trans in MR_Trans.objects.all().order_by('-id')[:5]:
                        mr = trans.mr_hd
                        servicing_materials.append({
                            'part': trans.name,
                            'quantity': float(trans.quantity) if trans.quantity else 0.0,
                            'car_no': mr.service_card.cardno if mr and mr.service_card else 'N/A',
                            'reason': mr.remarks or 'N/A',
                            'owner': mr.owner.username if mr and mr.owner else 'Public'
                        })

                    servicing_report = {
                        'pending_requests': servicing_pending_materials,
                        'recent_requests': servicing_materials,
                    }
                except Exception as e:
                    servicing_report = {'error': str(e)}

                success_response['message'] = {
                    'ssml': ssml_report,
                    'logistics': logistics_report,
                    'crm': crm_report,
                    'hrm': hrm_report,
                    'cmms': cmms_report,
                    'servicing_mr': servicing_report,
                }
                response = success_response

            elif module == 'profile':
                pk = data.get('mypk')
                try:
                    user_obj = User.objects.get(pk=pk)
                    addon = UserAddOns.objects.filter(user=user_obj).first()

                    from employee.models import Documents, EmployeeDocuments

                    compliance_types = Documents.objects.all()
                    compliance_items = EmployeeDocuments.objects.filter(user=user_obj)

                    items_map = {item.document.pk: item for item in compliance_items}

                    compliance_list = []
                    for ct in compliance_types:
                        item = items_map.get(ct.pk)
                        compliance_list.append({
                            'pk': ct.pk,
                            'title': ct.title,
                            'description': ct.description,
                            'required': ct.required,
                            'uploaded': item is not None,
                            'status': item.status if item else 'Not Uploaded',
                            'remark': item.remark if item else '',
                            'file_url': item.file.url if (item and item.file) else '',
                            'created_at': str(item.created_at) if item else '',
                        })

                    profile_data = {
                        'pk': user_obj.pk,
                        'username': user_obj.username,
                        'first_name': user_obj.first_name,
                        'last_name': user_obj.last_name,
                        'fullname': f"{user_obj.first_name} {user_obj.last_name}",
                        'email': user_obj.email,
                        'phone': addon.phone if addon else '',
                        'company': addon.company if addon else '',
                        'bio_id': addon.bio_id if addon else '',
                        'profile_pic': addon.profile_pic.url if (addon and addon.profile_pic and hasattr(addon.profile_pic, 'url')) else (addon.profile_pic if addon else 'static/assets/img/users/default.png'),
                        'public_link': f"/u/{user_obj.username}/",
                        'compliance': compliance_list
                    }

                    success_response['message'] = profile_data
                    response = success_response
                except Exception as e:
                    response['status_code'] = 500
                    response['message'] = str(e)

            elif module == 'auth':
                username = data.get('username')
                password = data.get('password') or data.get('key') # Support both
                next_url = data.get('next') or '/stream/' # Default to stream if no next
                source = data.get('source','app')
                # check if user exist
                user = authenticate(request, username=username, password=password)

                try:
                    # check if user is valid
                    if user is not None and hasattr(user, 'is_active') and user.is_active:
                        auth_login(request, user)
                        # Redirect to a success page.
                        new_token = generate_api_key()
                        user_detail = UserAddOns.objects.get(user=user)
                        logistics_permission = user_detail.is_logistic_admin()
                        if user_detail.api_token is None:
                            user_detail.api_token = new_token
                            user_detail.save()
                            api_token = new_token
                        else:
                            api_token = user_detail.api_token

                        msg = {
                            'auth': 'yes',
                            'pk': user.pk,
                            'username': user.username,
                            'redirect': next_url,
                            'api_token':api_token,
                            'logistics_permission':logistics_permission
                        }
                    else:
                        msg = {
                            'auth': 'no',
                            'error': "Invalid credentials or inactive account"
                        }

                except Exception as e:
                    msg = {
                        'auth': 'no',
                        'error': str(e)
                    }
                success_response['message'] = msg
                response = success_response

            elif module == 'users':

                all_users = User.objects.all()
                us = []
                for u in all_users:
                    obj = {
                        'pk': u.pk,
                        'username': u.username,
                        'fullname': f"{u.first_name} {u.last_name}"
                    }
                    us.append(obj)

                success_response['message'] = us
                response = success_response

            elif module == 'users_with_adon':
                all_users = UserAddOns.objects.all()
                us = []
                for usx in all_users:
                    obj = {
                        'pk': usx.pk,
                        'username': usx.user.username,
                        'fullname': f"{usx.user.first_name} {usx.user.last_name}",
                        'phone':usx.phone,
                        'email':usx.user.email,
                        'department':""
                    }
                    us.append(obj)

                success_response['message'] = us
                response = success_response

            elif module == 'cronjob':
                import datetime
                # Get the current time
                current_time = datetime.datetime.now().time()

                # Convert the current time to a string if needed
                current_time_str = current_time.strftime("%H:%M:%S")

                scripts = '/path/to/scripts/'
                # get jobs
                jobs = [
                    {
                        'name': 'hello-always',
                        'type': 'always',
                        'time': '00:00',
                        'exe': 'sync_html.sh'
                    },
                    {
                        'name': 'hello-sometime',
                        'type': 'timed',
                        'time': '12:00',
                        'exe': 'sync_emails.sh'
                    }
                ]

                # loop through Jobs
                for job in jobs:
                    j_name = job['name']
                    j_type = job['type']
                    j_time = job['time']
                    j_script = job['exe']
                    exe_script = f"{scripts}{j_script}"

                    if j_type == 'always' or (j_type == 'timed' and j_time >= current_time_str):
                        execute_script(exe_script)

            elif module == 'mail_senders':
                arr = []
                senders = MailSenders.objects.all()

                for sender in senders:
                    arr.append({
                        'host': sender.host,
                        'port': sender.port,
                        'address': sender.address,
                        'pk': sender.pk
                    })

                success_response['message'] = arr
                response = success_response

            elif module == 'bank_accounts':
                pk = data.get('pk','*')
                if pk == '*':
                    response['message'] = [acct.obj() for acct in BankAccounts.objects.all().order_by('acct_name')]
                else:
                    response['message'] = [acct.obj() for acct in BankAccounts.objects.get(pk=pk)]

                response['status_code'] = 200

            else:
                response['status_code'] = 503
                response['message'] = f"UNKNOWN MODULE ( METHOD : {method}, MODULE : {module} )"

        elif method == 'PATCH':  # update
            if module == 'user_permission':
                key = data.get('user')
                codename = data.get('codename')
                task = data.get('task')

                permission = Permission.objects.get(codename=codename)
                if User.objects.filter(pk=key).count() == 1:
                    user = User.objects.get(pk=key)
                    # Grant the permission to the user
                    if task == 'assign':
                        user.user_permissions.add(permission)
                        success_response['message'] = f"{codename} assigned to {user.username}"
                    elif task == 'remove':
                        user.user_permissions.remove(permission)
                        success_response['message'] = f"{codename} removed from {user.username}"
                    response = success_response

            elif module == 'reminder':
                date = data.get('date')
                time = data.get('time')
                title = data.get('title')
                message = data.get('message')
                key = data.get('pk')
                status = data.get('status')
                task = data.get('task')

                reminder = Reminder.objects.get(pk=key)
                if task == 'all':
                    reminder.rem_time = time
                    reminder.rem_date = date
                    reminder.title = title
                    reminder.message = message
                    success_response['message'] = "Reminder Updated"
                elif task == 'status':

                    if status == 'enable':
                        reminder.status = 1
                        success_response['message'] = "Reminder Disabled"
                    elif status == 'disable':
                        reminder.status = 0
                        success_response['message'] = "Reminder Enabled"
                    else:
                        success_response['message'] = f"Unknown status ({status}) set to reminder"

                reminder.save()
                response = success_response

            elif module == 'change_evat_engine':
                evat_key = data.get('evat_key')
                loc_key = data.get('loc_key')

                location = Locations.objects.get(pk=loc_key)
                evat_engine = EvatCredentials.objects.get(pk=evat_key)

                server_ip = location.ip_address
                db = location.db
                db_user = location.db_user
                db_pass = location.db_password

                company_name = evat_engine.company_name
                company_tin = evat_engine.company_tin
                company_security_key = evat_engine.company_security_key
                inv_req = evat_engine.inv_req
                z_rez = evat_engine.z_rez

                # connect to db
                import pyodbc

                # Create a connection string
                connection_str = (
                    "DRIVER={ODBC Driver 17 for SQL Server};"
                    f"SERVER={server_ip};"
                    f"DATABASE={db};"
                    f"UID={db_user};"
                    f"PWD={db_pass};"
                )
                # Create a connection
                connection = pyodbc.connect(connection_str)

                cursor = connection.cursor()
                cursor.execute(f"update sys_settings set sec_value = '{company_name}' where sec_key = 'COMPANY_NAMES'")

                cursor.execute(f"update sys_settings set sec_value = '{company_tin}' where sec_key = 'COMPANY_TIN'")

                cursor.execute(
                    f"update sys_settings set sec_value = '{company_security_key}' where sec_key = 'COMPANY_SECURITY_KEY'")

                cursor.execute(f"update sys_settings set sec_value = '{inv_req}' where sec_key = 'Evat_InvoiceReqApi'")

                cursor.execute(f"update sys_settings set sec_value = '{z_rez}' where sec_key = 'Evat_ZRepApi_url'")

                cursor.commit()
                cursor.close()

                connection.close()

                success_response['message'] = f"{location.descr} evat set to {evat_engine.server_location}"

                location.evat_key = evat_key
                location.save()

                response = success_response

            elif module == 'rest_password':
                pk = data.get('user')
                user = User.objects.get(pk=pk)
                if not UserAddOns.objects.filter(user=user).exists():
                    UserAddOns.objects.create(
                        user=user,

                    )
                addon = UserAddOns.objects.get(user=user)
                # generate new password
                new_password = generate_random_password()
                user.set_password(new_password)



                domain = request.get_host()
                email_template = f"""
                <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #0077be; border-radius: 10px; overflow: hidden;">
                    <div style="background-color: #0077be; padding: 25px; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 24px; letter-spacing: 1px;">OCEAN PORTAL</h1>
                        <p style="color: #e0f2ff; margin: 5px 0 0 0; font-size: 14px;">Security Notification</p>
                    </div>
                    <div style="padding: 30px; background-color: #ffffff;">
                        <p style="font-size: 16px; margin-bottom: 20px;">Dear <strong>{user.get_full_name()}</strong>,</p>
                        <p style="font-size: 15px; color: #555;">Your password has been successfully reset. Please use the credentials provided below to access the portal:</p>
                        
                        <div style="background-color: #f0f8ff; border-left: 4px solid #0077be; padding: 20px; margin: 25px 0; border-radius: 0 5px 5px 0;">
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 5px 0; color: #666; width: 100px;">Username:</td>
                                    <td style="padding: 5px 0; font-weight: bold;">{user.username}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px 0; color: #666;">Email:</td>
                                    <td style="padding: 5px 0; font-weight: bold;">{user.email}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px 0; color: #666;">Password:</td>
                                    <td style="padding: 5px 0; font-weight: bold; color: #0077be; font-family: 'Courier New', monospace; font-size: 18px;">{new_password}</td>
                                </tr>
                            </table>
                        </div>

                        <div style="text-align: center; margin-top: 35px;">
                            <a href="http://{domain}" style="background-color: #0077be; color: white; padding: 14px 35px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px; display: inline-block; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">Log in to OCEAN</a>
                        </div>
                    </div>
                    <div style="background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #888; border-top: 1px solid #eee;">
                        <p style="margin: 0 0 5px 0;">If you did not request this password reset, please contact the IT department immediately.</p>
                        <p style="margin: 0;">&copy; Ocean. All rights reserved.</p>
                    </div>
                </div>
                """


                sms_message = (f"Your password for ocean has been reset, please logon using the crecentials below \n"
                               f"USERNAME: {user.username}\n"
                               f"Password:{new_password}")
                mail_api = MailSenders.objects.get(is_default=True)
                user.save()
                mail_enc = make_md5_hash(email_template)
                MailQueues(sender=mail_api, recipient=user.email, cc='solomon@snedaghana.com',
                           subject="PASSWORD RESET FOR OCEAN", body=email_template,mail_key=mail_enc).save()

                Sms(api=SmsApi.objects.get(is_default=1), to=addon.phone, message=sms_message).save()

            elif module == 'all_password_reset':
                users = UserAddOns.objects.all()
                for u in users:
                    us = u.user
                    # generate new password
                    new_password = generate_random_password()
                    us.set_password(new_password)

                    email_template = (
                        f"Dear {us.get_full_name()}, your password has been reset to <strong>{new_password}</strong>."
                        f" Logon to <a href='http://ocean.snedaghana.loc'>OCEAN</a> with credentials below<br>"
                        f"<strong>Username</strong> : {us.username}<br>"
                        f"<strong>Email</strong> : {us.email}<br>"
                        f"<strong>Password</strong> : {new_password}<br>")
                    sms_message = (
                        f"Your password for ocean has been reset, please logon using the crecentials below \n"
                        f"USERNAME: {us.username}\n"
                        f"Password:{new_password}")
                    mail_api = MailSenders.objects.get(is_default=True)
                    us.save()
                    MailQueues(sender=mail_api, recipient=us.email, cc='solomon@snedaghana.com',
                               subject="PASSWORD RESET FOR OCEAN", body=email_template).save()
                    Sms(api=SmsApi.objects.get(is_default=1), to=user.phone, message=sms_message).save()

                success_response['message'] = "All Passwords Reset"
                response = success_response

            elif module == 'change_entity_type':
                mypk = data.get('mypk')
                entity_type_id = data.get('entity_type')
                entity_type = BusinessEntityTypes.objects.get(pk=entity_type_id)
                loc_pk = data.get('loc_pk')
                location = Locations.objects.get(pk=loc_pk)
                location.entity = entity_type
                location.save()

                print(data)

                success_response['message'] = "ENTITY TYPE CHANGED"
                response = success_response

            elif module == "entity_type":
                entity_pk = data.get("entity_pk")
                entity_name = data.get("entity_name")
                entity_descr = data.get("entity_descr")
                company_pk = data.get("company")

                try:
                    entity = BusinessEntityTypes.objects.get(id=entity_pk)
                except BusinessEntityTypes.DoesNotExist:
                    response['message'] = "Object not found"
                    response['status_code'] = 404
                    return JsonResponse(response)

                entity.entity_type_name = entity_name
                entity.entity_type_descr = entity_descr
                if company_pk:
                    entity.company_id = company_pk

                entity.save()

                response = success_response

            elif module == "company":
                pk = data.get("pk")
                name = data.get("companyName")
                address = data.get("companyAddress")
                email = data.get("companyEmail")
                phone = data.get("companyPhone")

                try:
                    company = Company.objects.get(pk=pk)
                except Company.DoesNotExist:
                    response['status_code'] = 404
                    response['message'] = f"Company with ID {pk} not found"
                    return JsonResponse(response)

                # Check for duplicate name or email (if changed)
                if Company.objects.exclude(pk=pk).filter(name=name).exists():
                    response['status_code'] = 400
                    response['message'] = f"Company name '{name}' already exists"
                    return JsonResponse(response)

                if email and Company.objects.exclude(pk=pk).filter(email=email).exists():
                    response['status_code'] = 400
                    response['message'] = f"Company email '{email}' already exists"
                    return JsonResponse(response)

                # Update fields
                company.name = name
                company.address = address
                company.email = email
                company.phone = phone

                company.save()

                response = success_response
                response['message'] = f"Company '{company.name}' updated successfully"

            elif module == 'user':

                try:
                    pk = data.get('pk')
                    user = User.objects.get(pk=pk)

                    addon = UserAddOns.objects.get(user=user)
                    addon.bio_id = data.get('emp_code')
                    addon.save()

                    response['status_code'] = 200
                    response['message'] = f"Updated"
                    return JsonResponse(response)
                except Exception as e:
                    response['status_code'] = 500
                    response['message'] = str(e)
                    return JsonResponse(response)

            else:
                response['status_code'] = 503
                response['message'] = f"UNKNOWN MODULE ( METHOD : {method}, MODULE : {module} )"



        elif method == 'DELETE':  # delete

            if module == 'location':
                pk = data.get('pk')
                Locations.objects.get(pk=pk).delete()

                success_response['message'] = "LOCATION DELETED"
                response = success_response

            if module == 'entity_type':
                pk = data.get('pk')
                print(f"Deleting Entity Type with pk {pk}")
                if BusinessEntityTypes.objects.filter(pk=pk).count() == 0:
                    response['status_code'] = 404
                    response['message'] = "ENTITY TYPE NOT FOUND"
                    return JsonResponse(response)

                BusinessEntityTypes.objects.get(pk=pk).delete()

                success_response['message'] = "ENTITY TYPE DELETED"
                response = success_response

            if module == 'company':
                pk = data.get('pk')
                print(f"Deleting company Type with pk {pk}")

                if Company.objects.filter(pk=pk).count() == 0:
                    response['status_code'] = 404
                    response['message'] = "COMPANY NOT FOUND"
                else:
                    company = Company.objects.get(pk=pk)
                    if company.entites.exists():
                        response["message"] = "Company has entities try deleting them first"
                        return JsonResponse(response)
                    else:
                        company.delete()

                success_response['message'] = "COMPANY DELETED"
                response = success_response



        else:
            response['status_code'] = 503
            response['message'] = f"UKNOWN REQUEST METHOD ({module})"

    except Exception as e:
        error_type, error_instance, traceback = sys.exc_info()
        tb_path = traceback.tb_frame.f_code.co_filename
        line_number = traceback.tb_lineno

        response["status_code"] = 500
        response[
            "message"] = f"An error of type {error_type} occurred on line {line_number} in file {tb_path}. Details: {e}"
        print(str(e))

    return JsonResponse(response)
