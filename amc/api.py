
import json
import sys
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from admin_panel.anton import make_md5_hash
from amc.models import *
from django.utils import timezone
from admin_panel.models import Sms, SmsApi, UserAddOns



@csrf_exempt
def amc_interface(request):
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
            if module == 'group':
                name = data.get('name')
                created_by = User.objects.get(id=data.get('mypk'))
                Groups.objects.create(
                    name=name,
                    created_by=created_by
                )
                response = success_response

            elif module == 'asset':
                # INSERT_YOUR_CODE
                group = Groups.objects.get(pk=data.get('group'))
                name = data.get('name')
                model = data.get('model')
                serial = data.get('serial')
                assigned_to = None
                assigned_to_pk = data.get('assigned_to')

                if assigned_to_pk:
                    try:
                        assigned_to = User.objects.get(pk=assigned_to_pk)
                    except User.DoesNotExist:
                        assigned_to = None
                status = data.get('status', 'active')
                created_by = User.objects.get(pk=data.get('mypk'))  # The user creating the asset
                # INSERT_YOUR_CODE
                created_by_fullname = created_by.get_full_name() if hasattr(created_by, 'get_full_name') else created_by.username

                Asset.objects.create(
                    group=group,
                    name=name,
                    model=model,
                    serial=serial,
                    assigned_to=assigned_to,
                    status=status,
                    created_by=created_by
                )

                # INSERT_YOUR_CODE
                # Add an initial AssetTransaction record after Asset creation
                asset_instance = Asset.objects.latest('id')
                AssetTransaction.objects.create(
                    asset=asset_instance,
                    date=timezone.now(),
                    action='other',
                    performed_by=created_by,
                    notes=f"Asset created by {created_by_fullname}"
                )


                response = success_response

            elif module == 'assign':
                # INSERT_YOUR_CODE
                asset_pk = data.get('asset')
                user_pk = data.get('user')
                performer = User.objects.get(pk=data.get('mypk'))
                if not asset_pk or not user_pk:
                    raise Exception("Asset and user must be provided for assignment.")

                asset = Asset.objects.get(pk=asset_pk)
                assignee = User.objects.get(pk=user_pk)
                # Save old assignee (if needed for logs)
                old_assignee = asset.assigned_to.username if asset.assigned_to else None

                asset.assigned_to = assignee
                asset.is_assgned = True
                asset.save()

                # Log assignment transaction
                AssetTransaction.objects.create(
                    asset=asset,
                    date=timezone.now().date(),
                    action='assign',
                    performed_by=performer,
                    notes=f"Asset assigned to {assignee.get_full_name() if hasattr(assignee,'get_full_name') and assignee.get_full_name() else assignee.username}"
                )

                # make log or sms
                notif = ""
                try:
                    user_details = UserAddOns.objects.get(user=assignee)
                    phone = user_details.phone
                    email = assignee.email
                    
                    # INSERT_YOUR_CODE
                    message = f"Dear {assignee.get_full_name() if hasattr(assignee, 'get_full_name') and assignee.get_full_name() else assignee.username}, an asset ({asset.name}) has been assigned to you in the system."

                    # send sms
                    Sms.objects.create(
                        api=SmsApi.objects.get(is_default=True),
                        to=phone,
                        message=message
                    )

                    notif = "Notification Sent"
                except Exception as e:
                    notif = str(e)

                response = success_response
                response['message'] = f"Asset assigned to {assignee.get_full_name() if hasattr(assignee,'get_full_name') and assignee.get_full_name() else assignee.username} \n{notif}"

            elif module == 'specifications':
                asset = Asset.objects.get(pk=data.get('asset'))
                added_by = User.objects.get(pk=data.get('mypk'))
                new_count = 0
                update_count = 0
                for spec in data.get('specifications'):
                    key = spec.get('key')
                    value = spec.get('value')

                    if AssetSpecifications.objects.filter(asset=asset,key=key).exists():
                        # update
                        AssetSpecifications.objects.filter(asset=asset,key=key).update(
                            value=value,
                            added_by=added_by
                            )
                        update_count += 1
                    else:
                        # create
                        AssetSpecifications.objects.create(
                            key=key,
                            value=value,
                            added_by=added_by,
                            asset=asset
                        )
                        new_count += 1

                # Make a transaction log for each specification addition or update
                for spec in data.get('specifications'):
                    key = spec.get('key')
                    value = spec.get('value')
                    action_type = 'update' if AssetSpecifications.objects.filter(asset=asset, key=key).exists() else 'create'
                    AssetTransaction.objects.create(
                        asset=asset,
                        date=timezone.now().date(),
                        action='other',
                        performed_by=added_by,
                        notes=f"Specification {action_type}: {key} set to '{value}' by {added_by.get_full_name()}"
                    )
                
                # INSERT_YOUR_CODE
                # create an sms message for asset owner
                owner = asset.assigned_to
                if owner:
                    sms_message = f"Hello {owner.get_full_name() if hasattr(owner, 'get_full_name') and owner.get_full_name() else owner.username}, specification(s) for your asset '{asset.name}' have been altered. If you have any questions, please contact support."
                    adon = UserAddOns.objects.get(user=owner)
                    Sms.objects.create(
                        api=SmsApi.objects.get(is_default=True),
                        to=adon.phone,
                        message=sms_message
                    )
              
                    

                success_response['message'] = f"Specification Alteration Successful for {asset.name} with {new_count} added and {update_count} updates"
                response = success_response
                

            else:
                raise Exception(f"Unknown {method} {module}")

        elif method == 'VIEW':
            if module == 'group':
                pk = data.get('pk','*')
                if pk == '*':
                    success_response['message'] = [gp.obj() for gp in Groups.objects.all()]
                else:
                    success_response['message'] = [gp.obj() for gp in Groups.objects.filter(pk=pk)]
                
                response = success_response

            elif module == 'print_document':
                asset_pk = data.get('pk')
                # INSERT_YOUR_CODE
                import os
                from fpdf import FPDF
                from django.conf import settings

                asset = Asset.objects.get(pk=asset_pk)
                specifications = AssetSpecifications.objects.filter(asset=asset)

                class PDF(FPDF):
                    def header(self):
                        self.set_font('Arial', 'B', 16)
                        self.cell(0, 10, 'Asset Issue Note', ln=1, align='C')
                        self.ln(10)

                pdf = PDF(format='A4')
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.set_font("Arial", size=12)

                def label_value(label, value,line=0):
                    pdf.set_font("Arial", style='B', size=11)
                    pdf.cell(47, 8, label, border=0)
                    pdf.set_font("Arial", style='', size=11)
                    pdf.cell(47, 8, value, border=0, ln=line)

                # Asset Details Section
                label_value("Asset Name:", asset.name)
                label_value("Model:", asset.model,1)
                label_value("Serial Number:", asset.serial)
                label_value("Group:", asset.group.name if asset.group else "",1)
                label_value("Assigned To:", asset.assigned_to.get_full_name() if asset.assigned_to and hasattr(asset.assigned_to, "get_full_name") and asset.assigned_to.get_full_name() else (asset.assigned_to.username if asset.assigned_to else ""))
                label_value("Status:", asset.status,1)
                label_value("Created By:", asset.created_by.get_full_name() if asset.created_by and hasattr(asset.created_by, "get_full_name") and asset.created_by.get_full_name() else (asset.created_by.username if asset.created_by else ""))
                label_value("Created At:", asset.created_at.strftime('%Y-%m-%d %H:%M:%S') if asset.created_at else "",1)

                pdf.ln(8)
                pdf.set_font("Arial", 'B', 13)
                pdf.cell(0, 10, "Specifications", ln=1)
                pdf.set_font("Arial", size=11)

                # Specifications table header
                row_height = 8
                col_width_key = 60
                col_width_val = 130
                pdf.set_fill_color(200, 220, 255)
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(col_width_key, row_height, "Key", border=1, fill=True)
                pdf.cell(col_width_val, row_height, "Value", border=1, fill=True)
                pdf.ln(row_height)

                pdf.set_font("Arial", '', 11)
                for spec in specifications:
                    pdf.cell(col_width_key, row_height, str(spec.key), border=1)
                    pdf.cell(col_width_val, row_height, str(spec.value), border=1)
                    pdf.ln(row_height)

                pdf.ln(16)
                # Signature places
                pdf.set_font("Arial", 'B', 13)
                pdf.cell(190, 10, "Signatures", ln=1,align='C')
                pdf.ln(10)
                sig_y = pdf.get_y()
                width = 150
                # Create three columns: Director, HOD, Asset Owner
                col_width = width / 3.0
                offset = 8

                pdf.set_font("Arial", 'B', 11)
                pdf.cell(col_width, 10, "Director", border=0, align='C')
                pdf.cell(20, 10, "", border=0)
                pdf.cell(col_width, 10, "HOD", border=0, align='C')
                pdf.cell(20, 10, "", border=0)
                pdf.cell(col_width, 10, "Asset Owner", border=0, align='C')
                pdf.ln(18)
                # Lines
                x_start = pdf.l_margin
                line_y = pdf.get_y()
                for i in range(3):
                    pdf.set_xy(x_start + i * (col_width + 20), line_y)
                    pdf.cell(col_width, 8, "_" * 26, border=0, align='C')
                pdf.ln(20)

                # Save file (output as a saved file)
            
               
                filename = f"static/tmp/asset_{asset.pk}_details.pdf"
                pdf.output(filename)

                # Inform frontend of location
                success_response['message'] = filename
                response = success_response

            elif module == 'specifications':
                asset = Asset.objects.get(pk=data.get('pk'))
                success_response['message'] = [sp.obj() for sp in AssetSpecifications.objects.filter(asset=asset)]

                response = success_response

            else:
                raise Exception(f"Unknown {method} {module}")

        elif method == 'PATCH':
            pass

        elif method == 'DELETE':
            pass

        else:
            raise Exception(f"Unknow Method {method}")

    except Exception as e:
        error_type, error_instance, traceback = sys.exc_info()
        tb_path = traceback.tb_frame.f_code.co_filename
        line_number = traceback.tb_lineno
        response["status_code"] = 500
        response[
            "message"] = f"An error occurred on line {line_number} in file {tb_path}. Details: {e}"

    return JsonResponse(response, safe=False)
