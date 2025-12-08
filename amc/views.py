from django.http.response import HttpResponse
from django.shortcuts import render
from .models import *
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

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
