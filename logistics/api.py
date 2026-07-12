import json
import sys
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from numba.cpython.charseq import is_default

from admin_panel.anton import make_md5_hash
from admin_panel.models import Sms, SmsApi, MailQueues, MailSenders, UserAddOns
from blog.anton import make_md5
from logistics.models import Vehicle, Driver, DeliveryRequest, DeliveryLog, VehicleFuelTopUp, VehicleServicing
from ocean.settings import LOGISTIC_CONTACT


@csrf_exempt
def interface(request):
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



        if method == "PUT":
            if module == 'vehicle':
                plate_number = data.get('plate_number')
                description = data.get('description')
                capacity = data.get('capacity')
                owner = User.objects.get(pk=data.get('user'))



                Vehicle.objects.create(plate_number=plate_number,
                                       description=description,
                                       capacity=capacity,
                                       owner=owner,
                                       model=data.get('model'),
                                       manufacturer=data.get('manufacturer'),
                                       make_year=data.get('make_year'),
                                       fuel_type=data.get('fuel_type'),
                                       chassis=data.get('chassis')
                                       )
                success_response['message'] = Vehicle.objects.get(plate_number=plate_number).pk

            elif module == 'fuel_purchase':
                vehicle = Vehicle.objects.get(pk=data.get('pk'))
                trip_enc = data.get('trip_enc')
                trip = DeliveryRequest.objects.get(enc=trip_enc)
                amount = data.get('amount')
                rate = data.get('rate')
                litres = Decimal(amount) / Decimal(rate)
                user = User.objects.get(pk=data.get('mypk'))
                enc = make_md5(make_md5_hash(f"{vehicle.plate_number} {amount} {rate}"))
                VehicleFuelTopUp.objects.create(
                    vehicle=vehicle,
                    amount=amount,
                    rate=rate,
                    litres=litres,
                    user=user,
                    block=enc
                )

                print(enc)
                DeliveryLog.objects.create(
                    delivery=trip,
                    title="Fuel Top Up",
                    details=f"Fuel Purchase - Amount: {amount}, Rate: {rate}, Litres: {litres:.2f}",
                    user=user
                )

                success_response['message'] = enc



            elif module == 'driver':

                user = User.objects.get(pk=data.get('user'))
                name =user.get_full_name()
                ad_on = UserAddOns.objects.get(user=user)
                phone_number = ad_on.phone
                license_number = data.get('license_number')
                email = user.email

                Driver.objects.create(
                    name=name,phone_number=phone_number,license_number=license_number,email=email,user=user
                )

                Sms.objects.create(
                    api=SmsApi.objects.get(is_default=True),
                    to=phone_number,
                    message=f"Hello {user.get_full_name()}, You have been registered as a driver with the following details: \nName: {name} \nLicense Number: {license_number}"
                )



                success_response['message'] = Driver.objects.get(name=name,phone_number=phone_number,license_number=license_number,email=email).pk

            elif module == 'trip_log':
                enc = data.get('enc')
                title = data.get('title')
                details = data.get('details')
                user = User.objects.get(pk=data.get('user'))

                DeliveryLog.objects.create(
                    delivery=DeliveryRequest.objects.get(enc=enc),
                    title=title,
                    details=details,
                    user=user
                )

            elif module == 'vehicle_service_request':
                vehicle = Vehicle.objects.get(pk=data.get('pk'))
                stype = data.get('type')
                details = data.get('details')
                user = User.objects.get(pk=data.get('mypk'))
                for_mechanic = data.get('for_mechanic')

                VehicleServicing.objects.create(
                    vehicle=vehicle,
                    type=stype,
                    details=details,
                    user=user,
                    for_mechanic=for_mechanic,
                )

                response['message'] = 'Vehicle Service Request Added'

            elif module == 'delivery_request':
                requested_by = User.objects.get(pk=data.get('requested_by'))
                destination = data.get('destination')
                description = data.get('description')
                delivery_type = data.get('delivery_type')
                source = data.get('source')

                enc = make_md5(make_md5_hash(f"{requested_by.first_name} {requested_by.last_name} {description} {delivery_type}"))

                DeliveryRequest.objects.create(
                    requested_by=requested_by,
                    description=description,
                    destination=destination,
                    delivery_type=delivery_type,
                    enc=enc,
                    source=source,
                )

                # make sms or email
                Sms.objects.create(
                    api=SmsApi.objects.get(is_default=True),
                    to=LOGISTIC_CONTACT.get('phone'),
                    message=f"There is a new delivery ({delivery_type}) request by {requested_by.first_name} {requested_by.last_name}."
                )

                # send email
                MailQueues.objects.create(
                    mail_key=enc,
                    recipient=LOGISTIC_CONTACT.get('email'),
                    sender=MailSenders.objects.get(is_default=True),
                    subject="Delivery Request",
                    body=f"There is a There is a new delivery ({delivery_type}) request by {requested_by.first_name} {requested_by.last_name}. "
                )

                # add to log
                DeliveryLog.objects.create(
                    delivery=DeliveryRequest.objects.get(enc=enc),
                    title="Delivery Request",
                    details="Delivery Request",
                    user=requested_by,
                )

                success_response['message'] = 'Delivery Request Added'


            elif module == 'delivery_log':
                delivery = DeliveryRequest.objects.get(enc=data.get('delivery'))
                title = data.get('title')
                details = data.get('details')
                user = User.objects.get(pk=data.get('user'))

                DeliveryLog.objects.create(
                    delivery=delivery,
                    title=title,
                    details=details,
                    user=user
                )

                success_response['message'] = 'Log Added'

            else:
                raise Exception('Module Not Supported')

            response = success_response

        elif method == 'VIEW':
            if module == 'vehicle':

                pk = data.get('pk','*')
                if pk == '*':
                    success_response['message'] = [v.obj() for v in Vehicle.objects.all()]
                else:
                    success_response['message'] = [v.obj() for v in Vehicle.objects.filter(pk=pk)]

            elif module == 'auth':
                pass

            elif module == 'weekly_report':
                from datetime import datetime, timedelta

                today = datetime.now()
                # Default: current ISO week (Monday to Sunday)
                week_start = today - timedelta(days=today.weekday())
                week_end = week_start + timedelta(days=6)

                start_date = data.get('start_date', week_start.strftime('%Y-%m-%d'))
                end_date = data.get('end_date', week_end.strftime('%Y-%m-%d'))

                # KPI Summary
                total_requests = DeliveryRequest.objects.filter(request_date__date__range=[start_date, end_date]).count()
                total_completed = DeliveryRequest.objects.filter(status='delivered', arrival_time__date__range=[start_date, end_date]).count()
                total_pending = DeliveryRequest.objects.filter(status='pending', request_date__date__range=[start_date, end_date]).count()
                total_in_transit = DeliveryRequest.objects.filter(status='in_transit').count()
                total_cancelled = DeliveryRequest.objects.filter(status='cancelled', request_date__date__range=[start_date, end_date]).count()
                total_fuel_amount = VehicleFuelTopUp.objects.filter(date__range=[start_date, end_date]).aggregate(total=Sum('amount'))['total'] or 0
                total_fuel_litres = VehicleFuelTopUp.objects.filter(date__range=[start_date, end_date]).aggregate(total=Sum('litres'))['total'] or 0

                # Vehicle performance
                vehicle_performance = []
                for vehicle in Vehicle.objects.all():
                    v_fuel_litres = VehicleFuelTopUp.objects.filter(vehicle=vehicle, date__range=[start_date, end_date]).aggregate(s=Sum('litres'))['s'] or 0
                    v_fuel_amount = VehicleFuelTopUp.objects.filter(vehicle=vehicle, date__range=[start_date, end_date]).aggregate(s=Sum('amount'))['s'] or 0
                    v_trips = DeliveryRequest.objects.filter(vehicle=vehicle, status='delivered', arrival_time__date__range=[start_date, end_date]).count()
                    vehicle_performance.append({
                        'pk': vehicle.pk,
                        'plate_number': vehicle.plate_number,
                        'model': vehicle.model,
                        'manufacturer': vehicle.manufacturer,
                        'trips_completed': v_trips,
                        'fuel_litres': float(v_fuel_litres),
                        'fuel_amount': float(v_fuel_amount),
                    })

                # Driver performance
                driver_performance = []
                for driver in Driver.objects.all():
                    d_assigned = DeliveryRequest.objects.filter(driver=driver, request_date__date__range=[start_date, end_date]).count()
                    d_delivered = DeliveryRequest.objects.filter(driver=driver, status='delivered', arrival_time__date__range=[start_date, end_date]).count()
                    d_transit = DeliveryRequest.objects.filter(driver=driver, status='in_transit').count()
                    d_pending = DeliveryRequest.objects.filter(driver=driver, status='schedule').count()
                    driver_performance.append({
                        'pk': driver.pk,
                        'name': driver.name,
                        'phone_number': driver.phone_number,
                        'assigned': d_assigned,
                        'delivered': d_delivered,
                        'in_transit': d_transit,
                        'pending': d_pending,
                    })

                # Detailed delivery log
                deliveries = DeliveryRequest.objects.filter(
                    request_date__date__range=[start_date, end_date]
                ).order_by('-request_date')
                delivery_log = [
                    {
                        'enc': req.enc,
                        'request_date': req.request_date.strftime('%Y-%m-%d %H:%M'),
                        'requested_by': req.requested_by.get_full_name() if req.requested_by else 'N/A',
                        'source': req.source,
                        'destination': req.destination,
                        'delivery_type': req.delivery_type,
                        'status': req.status,
                        'vehicle': req.vehicle.plate_number if req.vehicle else 'N/A',
                        'driver': req.driver.name if req.driver else 'N/A',
                        'departure_time': req.departure_time.strftime('%Y-%m-%d %H:%M') if req.departure_time else None,
                        'arrival_time': req.arrival_time.strftime('%Y-%m-%d %H:%M') if req.arrival_time else None,
                        'duration': req.duration(),
                    }
                    for req in deliveries
                ]

                if data.get('export') == 'pdf':
                    from fpdf import FPDF
                    import os
                    pdf = FPDF()
                    pdf.add_page('P')
                    pdf.set_margins(10, 10, 10)
                    
                    # Header
                    pdf.set_font('Arial', 'B', 14)
                    pdf.cell(190, 8, 'FLEET WAVE LOGISTICS WEEKLY REPORT', 0, 1, 'C')
                    pdf.set_font('Arial', '', 10)
                    pdf.cell(190, 5, f"Period: {start_date} to {end_date}", 0, 1, 'C')
                    pdf.ln(5)
                    
                    # Summary Stats Table
                    pdf.set_font('Arial', 'B', 11)
                    pdf.cell(190, 6, 'SUMMARY STATISTICS', 0, 1, 'L')
                    pdf.set_font('Arial', 'B', 9)
                    pdf.cell(30, 6, 'TOTAL REQUESTS', 1, 0, 'C')
                    pdf.cell(30, 6, 'COMPLETED', 1, 0, 'C')
                    pdf.cell(30, 6, 'PENDING', 1, 0, 'C')
                    pdf.cell(30, 6, 'IN TRANSIT', 1, 0, 'C')
                    pdf.cell(35, 6, 'TOTAL FUEL (L)', 1, 0, 'C')
                    pdf.cell(35, 6, 'FUEL AMOUNT', 1, 1, 'C')
                    
                    pdf.set_font('Arial', '', 9)
                    pdf.cell(30, 6, str(total_requests), 1, 0, 'C')
                    pdf.cell(30, 6, str(total_completed), 1, 0, 'C')
                    pdf.cell(30, 6, str(total_pending), 1, 0, 'C')
                    pdf.cell(30, 6, str(total_in_transit), 1, 0, 'C')
                    pdf.cell(35, 6, f"{total_fuel_litres:.1f} L", 1, 0, 'C')
                    pdf.cell(35, 6, f"GHS {total_fuel_amount:.2f}", 1, 1, 'C')
                    pdf.ln(8)
                    
                    # Vehicle Performance Table
                    pdf.set_font('Arial', 'B', 11)
                    pdf.cell(190, 6, 'VEHICLE PERFORMANCE', 0, 1, 'L')
                    pdf.set_font('Arial', 'B', 9)
                    pdf.cell(45, 6, 'PLATE NUMBER', 1, 0, 'C')
                    pdf.cell(45, 6, 'MODEL', 1, 0, 'C')
                    pdf.cell(35, 6, 'TRIPS COMPLETED', 1, 0, 'C')
                    pdf.cell(30, 6, 'FUEL LITRES', 1, 0, 'C')
                    pdf.cell(35, 6, 'FUEL AMOUNT', 1, 1, 'C')
                    
                    pdf.set_font('Arial', '', 9)
                    for vp in vehicle_performance:
                        pdf.cell(45, 6, vp['plate_number'], 1, 0, 'C')
                        pdf.cell(45, 6, f"{vp['manufacturer'].upper()} {vp['model']}", 1, 0, 'C')
                        pdf.cell(35, 6, str(vp['trips_completed']), 1, 0, 'C')
                        pdf.cell(30, 6, f"{vp['fuel_litres']:.1f} L", 1, 0, 'C')
                        pdf.cell(35, 6, f"GHS {vp['fuel_amount']:.2f}", 1, 1, 'C')
                    pdf.ln(8)
                    
                    # Driver Performance Table
                    pdf.set_font('Arial', 'B', 11)
                    pdf.cell(190, 6, 'DRIVER PERFORMANCE', 0, 1, 'L')
                    pdf.set_font('Arial', 'B', 9)
                    pdf.cell(50, 6, 'DRIVER NAME', 1, 0, 'C')
                    pdf.cell(35, 6, 'PHONE NUMBER', 1, 0, 'C')
                    pdf.cell(25, 6, 'ASSIGNED', 1, 0, 'C')
                    pdf.cell(25, 6, 'DELIVERED', 1, 0, 'C')
                    pdf.cell(25, 6, 'IN TRANSIT', 1, 0, 'C')
                    pdf.cell(30, 6, 'PENDING', 1, 1, 'C')
                    
                    pdf.set_font('Arial', '', 9)
                    for dp in driver_performance:
                        pdf.cell(50, 6, dp['name'], 1, 0, 'C')
                        pdf.cell(35, 6, dp['phone_number'], 1, 0, 'C')
                        pdf.cell(25, 6, str(dp['assigned']), 1, 0, 'C')
                        pdf.cell(25, 6, str(dp['delivered']), 1, 0, 'C')
                        pdf.cell(25, 6, str(dp['in_transit']), 1, 0, 'C')
                        pdf.cell(30, 6, str(dp['pending']), 1, 1, 'C')
                    
                    # Output PDF
                    file_name = f"static/general/tmp/weekly_report_{start_date}_{end_date}.pdf"
                    os.makedirs(os.path.dirname(file_name), exist_ok=True)
                    pdf.output(file_name)
                    
                    success_response['message'] = {
                        'pdf_url': file_name
                    }
                else:
                    success_response['message'] = {
                        'period': {'start_date': start_date, 'end_date': end_date},
                        'summary': {
                            'total_requests': total_requests,
                            'completed': total_completed,
                            'pending': total_pending,
                            'in_transit': total_in_transit,
                            'cancelled': total_cancelled,
                            'fuel_amount': float(total_fuel_amount),
                            'fuel_litres': float(total_fuel_litres),
                        },
                        'vehicle_performance': vehicle_performance,
                        'driver_performance': driver_performance,
                        'delivery_log': delivery_log,
                    }



            elif module == 'dashboard':
                from datetime import datetime, timedelta

                today = datetime.now()
                # Default: current ISO week (Monday to Sunday)
                week_start = today - timedelta(days=today.weekday())
                week_end = week_start + timedelta(days=6)

                start_date = data.get('start_date', week_start.strftime('%Y-%m-%d'))
                end_date = data.get('end_date', week_end.strftime('%Y-%m-%d'))

                # Overall KPIs
                total_requests = DeliveryRequest.objects.filter(request_date__date__range=[start_date, end_date]).count()
                total_completed = DeliveryRequest.objects.filter(status='delivered', arrival_time__date__range=[start_date, end_date]).count()
                total_pending = DeliveryRequest.objects.filter(status='pending').count()
                total_in_transit = DeliveryRequest.objects.filter(status='in_transit').count()
                total_scheduled = DeliveryRequest.objects.filter(status='schedule').count()
                total_cancelled = DeliveryRequest.objects.filter(status='cancelled', request_date__date__range=[start_date, end_date]).count()
                total_fuel_amount = VehicleFuelTopUp.objects.filter(date__range=[start_date, end_date]).aggregate(total=Sum('amount'))['total'] or 0
                total_fuel_litres = VehicleFuelTopUp.objects.filter(date__range=[start_date, end_date]).aggregate(total=Sum('litres'))['total'] or 0

                # Fleet status
                fleet_summary = {
                    'total': Vehicle.objects.count(),
                    'available': Vehicle.objects.filter(status='available').count(),
                    'in_use': Vehicle.objects.filter(status='in_use').count(),
                    'maintenance': Vehicle.objects.filter(status='maintenance').count(),
                    'inactive': Vehicle.objects.filter(status='inactive').count(),
                }

                # Driver status
                driver_summary = {
                    'total': Driver.objects.count(),
                    'available': Driver.objects.filter(status='available').count(),
                    'on_trip': Driver.objects.filter(status='on_trip').count(),
                    'inactive': Driver.objects.filter(status='inactive').count(),
                }

                # Deliveries by type (in period)
                by_type = {}
                for choice_key, _ in DeliveryRequest.type_choices:
                    by_type[choice_key] = DeliveryRequest.objects.filter(
                        delivery_type=choice_key,
                        request_date__date__range=[start_date, end_date]
                    ).count()

                # Recent 10 deliveries (all time)
                recent_deliveries = [
                    {
                        'enc': req.enc,
                        'request_date': req.request_date.strftime('%Y-%m-%d %H:%M'),
                        'requested_by': req.requested_by.get_full_name() if req.requested_by else 'N/A',
                        'source': req.source,
                        'destination': req.destination,
                        'delivery_type': req.delivery_type,
                        'status': req.status,
                        'vehicle': req.vehicle.plate_number if req.vehicle else 'N/A',
                        'driver': req.driver.name if req.driver else 'N/A',
                    }
                    for req in DeliveryRequest.objects.order_by('-request_date')[:10]
                ]

                success_response['message'] = {
                    'period': {'start_date': start_date, 'end_date': end_date},
                    'kpis': {
                        'total_requests': total_requests,
                        'completed': total_completed,
                        'pending': total_pending,
                        'in_transit': total_in_transit,
                        'scheduled': total_scheduled,
                        'cancelled': total_cancelled,
                        'fuel_amount': float(total_fuel_amount),
                        'fuel_litres': float(total_fuel_litres),
                    },
                    'fleet': fleet_summary,
                    'drivers': driver_summary,
                    'by_delivery_type': by_type,
                    'recent_deliveries': recent_deliveries,
                }


            elif module == 'driver':
                pk = data.get('pk','*')
                if pk == '*':
                    success_response['message'] = [v.obj() for v in Driver.objects.all()]
                else:
                    success_response['message'] = [v.obj() for v in Driver.objects.filter(pk=pk)]

            elif module == 'delivery_request':
                # DeliveryRequest.objects.all().delete()
                print(data)
                pk = data.get('pk', '*')

                if pk == '*':
                    result = DeliveryRequest.objects.all()

                    status = data.get('status', '*')
                    if status != '*':
                        if data.get('against') == 'in':
                            result = result.filter(status=status)
                        else:
                            result = result.exclude(status=status)

                    result = result.order_by('-request_date')

                    # Ensure limit is an integer
                    limit = int(data.get('limit', 100))
                    result = result[:limit]


                    success_response['message'] = [v.obj() for v in result]
                else:
                    success_response['message'] = [v.obj() for v in DeliveryRequest.objects.filter(enc=pk)] if DeliveryRequest.objects.filter(enc=pk).exists() else []

            else:
                raise Exception('Module Not Supported')
            response = success_response

        elif method == 'PATCH':
            if module == 'delivery_request':
                enc = data.get('enc')
                user = User.objects.get(pk=data.get('user'))
                status = data.get('status')
                delivery = DeliveryRequest.objects.get(enc=enc)
                remarks = data.get('remarks')


                DeliveryLog.objects.create(
                    delivery=delivery,
                    title=f"{status.replace('_', ' ').title()}",
                    details=remarks,
                    user=user
                )

                # Send SMS to requested person
                Sms.objects.create(
                    api=SmsApi.objects.get(is_default=True),
                    to=user.username,
                    message=f"Your delivery request status has been updated to {status}."
                )

                if status == 'schedule':
                    delivery.driver = Driver.objects.get(pk=data.get('driver'))
                    delivery.schedule_date = data.get('schedule_date')

                if status == 'in_transit':
                    delivery.vehicle = Vehicle.objects.get(pk=data.get('vehicle'))
                    delivery.departure_time = data.get('in_transit_date')
                
                if status == 'delivered':
                    delivery.arrival_time = data.get('end_time')

                delivery.status = status
                delivery.save()


                success_response['message'] = 'Delivery Request Updated'

            response = success_response

        else:
            raise Exception('Method Not Supported')





    except Exception as e:
        error_type, error_instance, traceback = sys.exc_info()
        tb_path = traceback.tb_frame.f_code.co_filename
        line_number = traceback.tb_lineno
        response["status_code"] = 500
        response[
            "message"] = f"An error occurred on line {line_number} in file {tb_path}. Details: {e}"

    return JsonResponse(response, safe=False)