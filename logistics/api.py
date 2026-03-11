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
                    
            elif module == 'weekly_report':
                import fpdf
                from datetime import datetime, timedelta
                import os

                class ModernReport(fpdf.FPDF):
                    def header(self):
                        # Logo
                        logo_path = os.path.join('static', 'general', 'img', 'logo.png')
                        if os.path.exists(logo_path):
                            self.image(logo_path, 10, 8, 33)
                        
                        self.set_font('Arial', 'B', 20)
                        self.set_text_color(44, 62, 80) # Dark Blue
                        self.cell(0, 10, 'WEEKLY LOGISTICS REPORT', 0, 1, 'R')
                        
                        self.set_font('Arial', 'I', 10)
                        self.set_text_color(127, 140, 141) # Grey
                        today = datetime.now().strftime('%B %d, %Y')
                        self.cell(0, 5, f'Generated on: {today}', 0, 1, 'R')
                        self.ln(15)

                    def footer(self):
                        self.set_y(-15)
                        self.set_font('Arial', 'I', 8)
                        self.set_text_color(149, 165, 166)
                        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

                    def styled_table_header(self, headers, widths):
                        self.set_fill_color(52, 152, 219) # Primary Blue
                        self.set_text_color(255, 255, 255)
                        self.set_font('Arial', 'B', 10)
                        for i, header in enumerate(headers):
                            self.cell(widths[i], 10, header, 1, 0, 'C', 1)
                        self.ln()

                today = datetime.now()
                start_date = (today - timedelta(days=today.weekday() + 1)).strftime('%Y-%m-%d')
                end_date = (today + timedelta(days=(5 - today.weekday()))).strftime('%Y-%m-%d')

                pdf = ModernReport()
                pdf.add_page()
                
                # Period Section
                pdf.set_font('Arial', 'B', 12)
                pdf.set_text_color(44, 62, 80)
                pdf.cell(0, 10, f'Reporting Period: {start_date} to {end_date}', 0, 1, 'L')
                pdf.ln(5)

                # SUMMARY HIGHLIGHTS (KPIs)
                pdf.set_fill_color(248, 249, 250)
                pdf.rect(10, pdf.get_y(), 190, 30, 'F')
                
                total_trips = DeliveryRequest.objects.filter(request_date__range=[start_date, end_date]).count()
                completed = DeliveryRequest.objects.filter(status='delivered', arrival_time__range=[start_date, end_date]).count()
                total_fuel = VehicleFuelTopUp.objects.filter(date__range=[start_date, end_date]).aggregate(total=Sum('amount'))['total'] or 0
                
                pdf.set_font('Arial', 'B', 10)
                pdf.set_text_color(127, 140, 141)
                pdf.cell(63, 10, 'TOTAL REQUESTS', 0, 0, 'C')
                pdf.cell(63, 10, 'COMPLETED', 0, 0, 'C')
                pdf.cell(63, 10, 'FUEL EXPENDITURE', 0, 1, 'C')
                
                pdf.set_font('Arial', 'B', 16)
                pdf.set_text_color(52, 152, 219)
                pdf.cell(63, 10, str(total_trips), 0, 0, 'C')
                pdf.cell(63, 10, str(completed), 0, 0, 'C')
                pdf.cell(63, 10, f"GHS {total_fuel:,.2f}", 0, 1, 'C')
                pdf.ln(15)

                # VEHICLE PERFORMANCE
                pdf.set_font('Arial', 'B', 12)
                pdf.set_text_color(44, 62, 80)
                pdf.cell(0, 10, 'Vehicle Performance Summary', 0, 1, 'L')
                
                headers = ['Plate Number', 'Model', 'Trips', 'Fuel (L)', 'Amount (GHS)']
                widths = [40, 50, 25, 35, 40]
                pdf.styled_table_header(headers, widths)
                
                pdf.set_font('Arial', '', 10)
                pdf.set_text_color(0, 0, 0)
                fill = False
                for vehicle in Vehicle.objects.all():
                    litres = VehicleFuelTopUp.objects.filter(vehicle=vehicle, date__range=[start_date, end_date]).aggregate(sum=Sum('litres'))['sum'] or 0
                    amount = VehicleFuelTopUp.objects.filter(vehicle=vehicle, date__range=[start_date, end_date]).aggregate(sum=Sum('amount'))['sum'] or 0
                    trips = vehicle.deliveryrequest_set.filter(status='delivered', arrival_time__range=[start_date, end_date]).count()
                    
                    pdf.set_fill_color(245, 245, 245)
                    pdf.cell(widths[0], 8, vehicle.plate_number, 1, 0, 'L', fill)
                    pdf.cell(widths[1], 8, vehicle.model[:20], 1, 0, 'L', fill)
                    pdf.cell(widths[2], 8, str(trips), 1, 0, 'C', fill)
                    pdf.cell(widths[3], 8, f"{litres:.2f}", 1, 0, 'R', fill)
                    pdf.cell(widths[4], 8, f"{amount:,.2f}", 1, 1, 'R', fill)
                    fill = not fill

                pdf.ln(10)

                # DRIVER ACTIVITY
                pdf.set_font('Arial', 'B', 12)
                pdf.set_text_color(44, 62, 80)
                pdf.cell(0, 10, 'Driver Performance', 0, 1, 'L')
                
                headers = ['Driver Name', 'Assigned', 'Delivered', 'In Transit', 'Pending']
                widths = [60, 30, 35, 35, 30]
                pdf.styled_table_header(headers, widths)
                
                pdf.set_font('Arial', '', 10)
                fill = False
                for driver in Driver.objects.all():
                    assigned = driver.deliveryrequest_set.filter(request_date__range=[start_date, end_date]).count()
                    delivered = driver.deliveryrequest_set.filter(status='delivered', arrival_time__range=[start_date, end_date]).count()
                    transit = driver.deliveryrequest_set.filter(status='in_transit').count()
                    pending = driver.deliveryrequest_set.filter(status='schedule').count()
                    
                    pdf.set_fill_color(245, 245, 245)
                    pdf.cell(widths[0], 8, driver.name[:30], 1, 0, 'L', fill)
                    pdf.cell(widths[1], 8, str(assigned), 1, 0, 'C', fill)
                    pdf.cell(widths[2], 8, str(delivered), 1, 0, 'C', fill)
                    pdf.cell(widths[3], 8, str(transit), 1, 0, 'C', fill)
                    pdf.cell(widths[4], 8, str(pending), 1, 1, 'C', fill)
                    fill = not fill

                # DETAILED LOG
                pdf.add_page()
                pdf.set_font('Arial', 'B', 12)
                pdf.set_text_color(44, 62, 80)
                pdf.cell(0, 10, 'Detailed Delivery Log', 0, 1, 'L')
                
                headers = ['Date', 'Requested By', 'From', 'To', 'Duration']
                widths = [30, 40, 50, 50, 20]
                pdf.styled_table_header(headers, widths)
                
                pdf.set_font('Arial', '', 9)
                fill = False
                for req in DeliveryRequest.objects.filter(request_date__range=[start_date, end_date]).order_by('-request_date'):
                    pdf.set_fill_color(245, 245, 245)
                    pdf.cell(widths[0], 7, str(req.request_date).split(' ')[0], 1, 0, 'L', fill)
                    pdf.cell(widths[1], 7, req.requested_by.get_full_name()[:20], 1, 0, 'L', fill)
                    pdf.cell(widths[2], 7, req.source[:25], 1, 0, 'L', fill)
                    pdf.cell(widths[3], 7, req.destination[:25], 1, 0, 'L', fill)
                    pdf.cell(widths[4], 7, str(req.duration())[:10], 1, 1, 'C', fill)
                    fill = not fill

                file_name = f"static/general/tmp/weekly_report_{start_date}_{end_date}.pdf"
                pdf.output(file_name, 'F')
                success_response['message'] = file_name
                success_response['message'] = file_name






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