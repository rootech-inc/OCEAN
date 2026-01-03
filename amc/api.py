
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
from admin_panel.models import Sms, SmsApi, UserAddOns, MailQueues, MailSenders,TicketHd
from ocean.settings import AMC_ASSIGN_COPIES
from employee.models import Documents,EmployeeDocuments
from ocean.settings import SHOW_ERROR_LINE


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

            elif module == 'group_requirement':
                document_select = data.get('document_select')
                group_id = data.get('group_id')
                mypk = data.get('mypk')

                created_by = User.objects.get(pk=mypk)
                document = Documents.objects.get(pk=document_select)
                group = Groups.objects.get(pk=group_id)

                GroupCompliance.objects.create(
                    document=document,
                    group=group,
                    created_by=created_by
                )

                # save



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

            elif module == 'service_request':
                description = data.get('description')
                
                asset = Asset.objects.get(pk=data.get('asset'))
                owner = asset.assigned_to if asset.assigned_to else None
                if not owner:
                    owner = User.objects.get(pk=data.get('mypk'))


                ref = asset.serial
                TicketHd(title=f"Service Request for {asset.name}", descr=description, owner=owner, app='AMC', ref=ref).save()
                        # sms
                smsapi = SmsApi.objects.get(is_default=1)
                Sms(api=smsapi, to='0546310011',
                            message=f"There is an issue with title 'Service Request for {asset.name}' reported by {owner.username}").save()

                success_response['message'] = "Service Request Reported"
                response = success_response

            elif module == 'assign':
                # INSERT_YOUR_CODE
                asset_pk = data.get('asset')
                user_pk = data.get('user')
                inform_management = data.get('inform_management','NO')

                performer = User.objects.get(pk=data.get('mypk'))
                if not asset_pk or not user_pk:
                    raise Exception("Asset and user must be provided for assignment.")

                asset = Asset.objects.get(pk=asset_pk)
                assignee = User.objects.get(pk=user_pk)

            
                # Check if the group has compliance requirements before allowing assignment
               
                group_compliancec = GroupCompliance.objects.filter(group=asset.group)
                if group_compliancec.exists():
                    for compliance in group_compliancec:
                        # check if user has compliance
                        if EmployeeDocuments.objects.filter(user=assignee,document=compliance.document).count() == 0:
                           raise Exception(f"{assignee.get_full_name()} does not have all required compliance documents ({compliance.document.title}).")

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
                    # INSERT_YOUR_CODE
                    # Compose an HTML-formatted email message with assign message and device details
                    message = f"""
                    <html>
                      <body>
                        <p>
                          Dear {assignee.get_full_name() if hasattr(assignee, 'get_full_name') and assignee.get_full_name() else assignee.username},
                        </p>
                        <p>
                          An asset has been <b>assigned</b> to you in the system.
                        </p>
                        <hr>
                        <h3>Asset Details</h3>
                        <table style="border-collapse: collapse;">
                          <tr>
                            <th align="left" style="border-bottom: 1px solid #ddd; padding: 6px;">Name</th>
                            <td style="padding: 6px;">{asset.name}</td>
                          </tr>
                          <tr>
                            <th align="left" style="border-bottom: 1px solid #ddd; padding: 6px;">Category</th>
                            <td style="padding: 6px;">{asset.group.name}</td>
                          </tr>
                          <tr>
                            <th align="left" style="border-bottom: 1px solid #ddd; padding: 6px;">Serial Number</th>
                            <td style="padding: 6px;">{asset.serial}</td>
                          </tr>
                          <tr>
                            <th align="left" style="border-bottom: 1px solid #ddd; padding: 6px;">Model</th>
                            <td style="padding: 6px;">{asset.model}</td>
                          </tr>
                        </table>
                        <hr>
                        <p>
                          Please acknowledge receiving the asset and ensure its care and proper usage as per company policies.
                        </p>
                        <p style="margin-top: 24px;">
                          Regards,<br>
                          Asset Management Team
                        </p>
                      </body>
                    </html>
                    """
                    # send sms
                    Sms.objects.create(
                        api=SmsApi.objects.get(is_default=True),
                        to=phone,
                        message=message
                    )
                    em_un = make_md5_hash(f"{email}-{message}-{asset.name}-{asset.serial}-{asset.model}-{asset.group.name}")
                    if inform_management == 'YES':
                        cc = AMC_ASSIGN_COPIES
                    else:
                        cc = ''
                    MailQueues.objects.create(
                        sender=MailSenders.objects.get(is_default=True),
                        recipient=email,
                        subject="Issue Of Company Asset",
                        body=message,
                        mail_key=em_un,
                        cc=cc
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
                

                asset = Asset.objects.get(pk=asset_pk)
                if asset.is_signed:
                    success_response['message'] = asset.signed_document.url.lstrip("/")if asset.signed_document else None
                    

                else :
                    import os
                    from fpdf import FPDF
                    from django.conf import settings
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
                    pdf.cell(col_width, 10, "Issued By", border=0, align='C')
                    pdf.cell(20, 10, "", border=0)
                    pdf.cell(col_width, 10, "Witness", border=0, align='C')
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

                    # INSERT_YOUR_CODE
                    # Add a new page for asset images, if asset images exist

                    images = list(AssetImages.objects.filter(asset=asset))
                    if images:
                        pdf.add_page()
                        pdf.set_font("Arial", 'B', 13)
                        pdf.cell(0, 10, "Asset Images", ln=1)
                        pdf.ln(6)
                        # Display images in rows, e.g. 3 per row
                        import os
                        images_per_row = 3
                        image_w = 50
                        image_h = 50
                        cell_margin = 5  # space between images
                        col_width = image_w + cell_margin

                        num_images = len(images)
                        row_images = []
                        for idx, img in enumerate(images):
                            try:
                                # Show caption, creator and created_at
                                caption = img.caption or ""
                                created_by = img.created_by.get_full_name() if img.created_by and hasattr(img.created_by, 'get_full_name') and img.created_by.get_full_name() else (img.created_by.username if img.created_by else "")
                                created_at = img.created_at.strftime('%Y-%m-%d %H:%M:%S') if img.created_at else ""
                                meta = f"Uploaded by: {created_by}, at: {created_at}"

                                # Gather per-image data
                                img_data = {
                                    'caption': caption,
                                    'meta': meta,
                                    'img': img,
                                }
                                row_images.append(img_data)

                                # When row full or last image, print the row
                                if len(row_images) == images_per_row or idx == num_images - 1:
                                    y_start = pdf.get_y()
                                    x_start = pdf.l_margin

                                    # Find max image height in the row (for consistency)
                                    max_height = image_h

                                    # Draw images for this row
                                    for i, row_img_data in enumerate(row_images):
                                        img_obj = row_img_data['img']
                                        img_path = img_obj.image.path if hasattr(img_obj.image, "path") else img_obj.image.url
                                        this_x = x_start + i * col_width
                                        pdf.set_xy(this_x, y_start)

                                        if os.path.exists(img_path):
                                            try:
                                                pdf.image(img_path, x=this_x, y=y_start, w=image_w, h=image_h)
                                            except Exception as e:
                                                pdf.set_font("Arial", 'I', 10)
                                                pdf.set_xy(this_x, y_start)
                                                pdf.set_text_color(255, 0, 0)
                                                pdf.multi_cell(image_w, 8, "[Img load error]", border=0)
                                                pdf.set_text_color(0, 0, 0)
                                        else:
                                            pdf.set_font("Arial", 'I', 10)
                                            pdf.set_xy(this_x, y_start)
                                            pdf.set_text_color(255, 0, 0)
                                            pdf.multi_cell(image_w, 8, "[Image file missing]", border=0)
                                            pdf.set_text_color(0, 0, 0)

                                    # Print captions below images
                                    y_caption = y_start + image_h + 2
                                    for i, row_img_data in enumerate(row_images):
                                        caption = row_img_data['caption']
                                        if caption:
                                            pdf.set_font("Arial", 'B', 10)
                                            pdf.set_xy(x_start + i * col_width, y_caption)
                                            pdf.multi_cell(image_w, 6, caption, border=0)
                                    # Print metadata below captions
                                    y_meta = y_caption + 10
                                    for i, row_img_data in enumerate(row_images):
                                        meta = row_img_data['meta']
                                        pdf.set_font("Arial", '', 8)
                                        pdf.set_xy(x_start + i * col_width, y_meta)
                                        pdf.multi_cell(image_w, 5, meta, border=0)
                                    # Move to next row after images, captions, meta
                                    pdf.set_y(y_meta + 15)
                                    pdf.ln(4)
                                    row_images = []
                            except Exception as e:
                                pdf.set_font("Arial", 'I', 10)
                                pdf.set_text_color(255, 0, 0)
                                pdf.cell(0, 8, f"[Error loading image: {e}]", ln=1)
                                pdf.set_text_color(0, 0, 0)
                                pdf.ln(8)

                
                
                    filename = f"static/general/tmp/asset_{asset.pk}_details.pdf"
                    pdf.output(filename)

                    # Inform frontend of location
                    success_response['message'] = filename
                response = success_response

            elif module == 'specifications':
                asset = Asset.objects.get(pk=data.get('pk'))
                success_response['message'] = [sp.obj() for sp in AssetSpecifications.objects.filter(asset=asset)]

                response = success_response

            elif module == 'images':
                asset = Asset.objects.get(pk=data.get('asset'))
                success_response['message'] = [img.obj() for img in AssetImages.objects.filter(asset=asset)]
                response = success_response

                response = success_response

            elif module == 'transactions':
                asset = Asset.objects.get(pk=data.get('asset'))
                success_response['message'] = [tx.obj() for tx in AssetTransaction.objects.filter(asset=asset)]
                response = success_response

            elif module == 'service_request':
                asset = Asset.objects.get(pk=data.get('asset'))
                success_response['message'] = [ticket.obj() for ticket in TicketHd.objects.filter(ref=asset.serial)]
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
        if SHOW_ERROR_LINE:
            response[
                "message"] = f"An error occurred on line {line_number} in file {tb_path}. Details: {e}"
        else:
            response['message'] = str(e)

    return JsonResponse(response, safe=False)
