from django.http.response import HttpResponse
from django.shortcuts import render
from .models import *
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from admin_panel.models import Sms, SmsApi, UserAddOns, MailQueues, MailSenders,TicketHd,MailAttachments
from django.utils import timezone
from admin_panel.anton import make_md5_hash
from employee.models import Documents

@login_required
def amc(request):
    context = {
        'nav':True,
        'assets':Asset.objects.all(),
        'comment':True
    }
    return render(request,'amc/index.html',context=context)

@login_required
def groups(request):
    context = {
        'nav':True,
        'groups':Groups.objects.all()
    }
    return render(request,'amc/groups.html',context=context)

@login_required
@csrf_exempt
def upload_asset_image(request):
    if request.method == 'POST':
        pk = request.POST.get('asset')
        image = request.FILES.get('image')
        caption = request.POST.get('caption')
        asset = Asset.objects.get(pk=pk)
        asset_image = AssetImages(asset=asset, image=image, caption=caption, created_by=request.user)
        asset_image.save()
        return JsonResponse({'status_code':200,'message': 'Image uploaded successfully'})
    return JsonResponse({'status_code':400,'message': 'Failed to upload image'})

@login_required
@csrf_exempt
def sign_reciept(request):
    if request.method == 'POST':
        pk = request.POST.get('asset')
        signed_document = request.FILES.get('signed_document')
        asset = Asset.objects.get(pk=pk)
        asset2keep = asset
        asset.signed_document = signed_document
        asset.is_signed = True
        asset.save()

        asset = Asset.objects.get(pk=pk)
        # add trasaction
        AssetTransaction.objects.create(
            action='other', 
            performed_by=request.user,
            date=timezone.now(),
            notes="Document Signed",
            asset=asset
        )

        # send email
        # Send an email to notify that the asset has been signed
        email = asset.assigned_to.email if asset.assigned_to else asset.created_by.email
        
        message = f"Dear {asset.assigned_to.get_full_name() if asset.assigned_to else asset.created_by.get_full_name()},<br><br>"
        message += f"The asset <strong>{asset.name}</strong> (Serial: {asset.serial}, Model: {asset.model}) has been signed.<br>"
        message += f"Group: {asset.group.name if asset.group else 'N/A'}<br><br>"
        message += "The signed document is now on file with your asset record.<br><br>"
        message += "Thank you.<br>Asset Management Team"

        em_un = make_md5_hash(f"{email}-{message}-{asset.name}-{asset.serial}-{asset.model}-{asset.group.name}")
        
        MailQueues.objects.create(
                        sender=MailSenders.objects.get(is_default=True),
                        recipient=email,
                        subject="Asset Signed",
                        body=message,
                        mail_key=em_un,
                        cc='nanayaa@snedamotors.com'
                    )
        # add attachment
        signed_document = asset.signed_document
        MailAttachments.objects.create(
            mail=MailQueues.objects.get(mail_key=em_un),
            attachment=signed_document
        )
        


        return JsonResponse({'status_code':200,'message': 'Asset Has Been Signed'})
    return JsonResponse({'status_code':400,'message': 'Failed to upload image'})


@login_required
def asset_group(request,name):
    # INSERT_YOUR_CODE
    from django.shortcuts import render, get_object_or_404
    from .models import Groups, Asset

   
    group = get_object_or_404(Groups, name=name)
    assets = Asset.objects.filter(group=group)
    context = {
            'nav': True,
            'page': {'title': f"Asset Group: {group.name}"},
            'group': group,
            'assets': assets,
            'documents':Documents.objects.all(),
            'group_compliance':GroupCompliance.objects.filter(group=group)
        }
    return render(request, 'amc/asset_group.html', context)