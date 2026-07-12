from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

from logistics.models import DeliveryRequest, Driver, Vehicle, VehicleFuelTopUp


@login_required
def home(request):
    # DeliveryRequest.objects.all().delete()
    # Driver.objects.all().delete()
    # Vehicle.objects.all().delete()

    context = {
        'nav':True,
        "page":{
            "title":"Logistics",
        }
    }

    return render(request,'logistics/index.html',context=context)

@login_required
def newdelivery(request):

    context = {
        'nav':True,
        "page":{
            "title":"Delivery Request",
        }
    }

    context['type_choices'] = DeliveryRequest.type_choices

    return render(request,'logistics/delivery_request.html',context=context)

@login_required
def delivery_details(request,enc):
    context = {
        'nav':True,
        "page":{
            "title":"Delivery Details",
        }
    }
    context['enc'] = enc
    context['car_pk'] = DeliveryRequest.objects.get(enc=enc).obj()['vehicle']['pk'] if DeliveryRequest.objects.filter(enc=enc).exists() else 0
    context['delivery'] = DeliveryRequest.objects.get(enc=enc)
    return render(request,'logistics/delivery_details.html',context=context)

@login_required
def drivers(request):

    context = {
        'nav':True,
        "page":{
            "title":"Drivers",
        }
    }

    return render(request,'logistics/drivers.html',context=context)


@login_required
@csrf_exempt
def upload_diver_image(request):
        if request.method == 'POST' and request.FILES.get('image'):
            try:
                from PIL import Image
                import io

                # ... in the upload_diver_image view
                driver_id = request.POST.get('driver')
                driver = Driver.objects.get(pk=driver_id)

                # Open the uploaded image using PIL
                image = Image.open(request.FILES['image'])

                # Convert to RGB if image is in RGBA mode
                if image.mode == 'RGBA':
                    image = image.convert('RGB')

                # Resize the image to 50x50 pixels using thumbnail
                image.thumbnail((100, 100))

                # Save the processed image to a bytes buffer
                buffer = io.BytesIO()
                image.save(buffer, format='JPEG')
                buffer.seek(0)
                
                # Create a new Django File object from the buffer
                from django.core.files import File
                processed_image = File(buffer, name=request.FILES['image'].name)
                
                # Save the processed image
                driver.image = processed_image
                driver.license = request.FILES['license']
                driver.save()
                messages.success(request, 'Driver image updated successfully')
            except Exception as e:
                messages.error(request, f'Error updating driver image: {str(e)}')
    
        return redirect('logistics-drivers')

@login_required
def fleet(request):

    last_fleet_pk = 0 if Vehicle.objects.all().count() == 0 else Vehicle.objects.all().last().pk
    context = {
        'nav':True,
        "page":{
            "title":"Fleet",
        },
        "last_fleet_pk":last_fleet_pk,
        "fleets":Vehicle.objects.all()
    }
    return render(request,'logistics/fleet.html',context=context)

@login_required
@csrf_exempt
def uploadfleetimage(request):
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            from PIL import Image
            import io
            fleet_id = request.POST.get('fleet_id')
            image = Image.open(request.FILES['image'])

            fleet = Vehicle.objects.get(pk=fleet_id)

            # Convert to RGB if image is in RGBA mode
            if image.mode == 'RGBA':
                image = image.convert('RGB')

            # Resize the image to 50x50 pixels using thumbnail
            image.thumbnail((100, 100))

            # Save the processed image to a bytes buffer
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG')
            buffer.seek(0)

            # Create a new Django File object from the buffer
            from django.core.files import File
            processed_image = File(buffer, name=request.FILES['image'].name)

            fleet.image = processed_image
            fleet.save()
            messages.success(request, 'Fleet image updated successfully')
            return redirect('logistics-fleet')
        except Exception as e:
            messages.error(request, f'Error updating fleet image: {str(e)}')
            return redirect('logistics-fleet')

@login_required()
def mydelivery(request):

    us = request.user
    print(us.pk)
    driver = Driver.objects.get(user=us)
    context = {
        'nav':False,
        "page":{
            "title":"My Trips",
        },
        'delivery_requests':DeliveryRequest.objects.filter(driver=driver).exclude(status='delivered').order_by('-scheduled_date')
    }
    return render(request,'logistics/my-deliveries.html',context=context)

@csrf_exempt
def fuel_reciept(request):
            if request.method == 'POST' and request.FILES.get('receipt'):
                try:
                    from PIL import Image
                    import io

                    # Get the delivery request using enc
                    delivery_enc = request.POST.get('block')
                    fuel_top_up = VehicleFuelTopUp.objects.get(block=delivery_enc)

                    # Process the uploaded image
                    image = Image.open(request.FILES['receipt'])

                    # Convert to RGB if image is in RGBA mode
                    if image.mode == 'RGBA':
                        image = image.convert('RGB')

                    # Resize the image while maintaining aspect ratio
                    image.thumbnail((800, 800))

                    # Save the processed image to a bytes buffer
                    buffer = io.BytesIO()
                    image.save(buffer, format='JPEG')
                    buffer.seek(0)

                    # Create a new Django File object from the buffer
                    from django.core.files import File
                    processed_image = File(buffer, name=request.FILES['receipt'].name)

                    # Update the delivery request with fuel receipt details
                    fuel_top_up.receipt = processed_image
                    fuel_top_up.save()

                    messages.success(request, 'Fuel receipt uploaded successfully')
                    return redirect(request.META.get('HTTP_REFERER', 'logistics-delivery-details'))

                except Exception as e:
                    print(e)
                    return HttpResponse(e, status=500)
                    messages.error(request, f'Error uploading fuel receipt: {str(e)}')
                    return redirect(request.META.get('HTTP_REFERER', 'logistics-delivery-details'))

            return redirect(request.META.get('HTTP_REFERER', 'logistics-delivery-details'))