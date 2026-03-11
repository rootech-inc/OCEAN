from ipaddress import ip_address
import json
import sys
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Device, Employee, AttendanceLog, Area, Department, Position,Resignation
from zk import ZK

@csrf_exempt
def api_interface(request):
    response = {
        'status_code': 0,
        'message': ""
    }

    success_response = {
        'status_code': 200,
        'message': "Procedure Completed Successfully"
    }

    method = request.method

    try:
        body = json.loads(request.body)
        module = body.get('module')
        data = body.get('data')

        # Area.objects.all().delete()
        # Department.objects.all().delete()
        # Position.objects.all().delete()

        if method == 'PUT':
            # Handle PUT requests
            if module == 'sync_users':
                sync_users = 0
                for device in Device.objects.all():
                    ip_address = device.ip_address
                    print(ip_address)
                    conn = ZK(ip_address, port=4370, timeout=5)  # use device IP from your logs
                    zk = None

                    if not Area.objects.filter(is_default=True).exists():
                        Area.objects.create(
                            is_default=True,
                            area_code='001',
                            area_name='Default',
                            work_start_time='08:15',
                            work_end_time='17:00',
                            how_many_off_days=1


                        )
                    
                    area = Area.objects.filter(is_default=True).first()

                    try:
                        zk = conn.connect()
                        users = zk.get_users()
                        for user in users:
                            Employee.objects.update_or_create(
                                user_id=str(user.user_id),
                                defaults={'name': user.name},
                                area=area

                            )
                            print(f"Synced: {user.user_id} - {user.name}")
                            sync_users += 1
                    except Exception as e:
                        print(f"Error: {e}")
                    finally:
                        if zk:
                            zk.disconnect()
                response['status_code'] = 200
                response['message'] = f"Synced {sync_users} users"
            
            elif module == 'sync_attendance':
                user_id = data.get('user_id')
                timestamp = data.get('timestamp')
                status = data.get('status')
                device_sn = data.get('device_sn')
                device = Device.objects.get(serial_number=device_sn)
                
                punch = data.get('punch')
                
                AttendanceLog.objects.create(
                    user_id=user_id,
                    timestamp=timestamp,
                    verify_type=status,
                    punch_state=punch,
                    device=device,
                    device_sn=device_sn

                )

                success_response['message'] = f"Attendance Synced"
                response = success_response

            elif module == 'recieve_user':
                uid = data.get('uid')
                name = data.get('name')
                area_name = data.get('area')

                if not Area.objects.filter(area_name=area_name).exists():
                    area_code = f"00{Area.objects.all().count() + 1}" if Area.objects.all().exists() else '001'
                    Area.objects.create(
                        area_code=str(area_code),
                        area_name=area_name,
                        is_default=False,
                        work_start_time='08:15',
                        work_end_time='17:00',
                        how_many_off_days=5
                    )

                area = Area.objects.filter(area_name=area_name).first()

                saved = 0
                not_saved = 0

                Employee.objects.update_or_create(
                        user_id=uid,
                        defaults={'name': name, 'area': area},
                    )
                response['status_code'] = 200
                response['message'] = f"User {uid} saved successfully"

            elif module == 'area':
                area_code = data.get('area_code')
                area_name = data.get('area_name')
                work_start_time = data.get('work_start_time')
                work_end_time = data.get('work_end_time')
                how_many_off_days = data.get('how_many_off_days')
                is_default = data.get('is_default')

                Area.objects.create(area_code=area_code, area_name=area_name, work_start_time=work_start_time, work_end_time=work_end_time, how_many_off_days=how_many_off_days, is_default=is_default)
                response['status_code'] = 200
                response['message'] = "Area created successfully"

            elif module == 'department':
                dept_code = data.get('dept_code')
                dept_name = data.get('dept_name')
                Department.objects.create(dept_code=dept_code, dept_name=dept_name)
                response['status_code'] = 200
                response['message'] = "Department created successfully"

            elif module == 'position':
                position_code = data.get('position_code')
                position_name = data.get('position_name')
                Position.objects.create(position_code=position_code, position_name=position_name)
                response['status_code'] = 200
                response['message'] = "Position created successfully"
            

        elif method == 'VIEW':
            # Handle VIEW (GET-like) requests
            if module == 'area':
                success_response['message'] = [ar.obj() for ar in Area.objects.all()]
                response = success_response
            elif module == 'department':
                success_response['message'] = [dp.obj() for dp in Department.objects.all()]
                response = success_response
            elif module == 'position':
                success_response['message'] = [ps.obj() for ps in Position.objects.all()]
                response = success_response

            elif module == 'employee':
                user_id = data.get('user_id','*')
                if user_id == '*':
                        success_response['message'] = [emp.obj() for emp in Employee.objects.filter(is_resigned=False)]
                else:
                    success_response['message'] = [emp.obj() for emp in Employee.objects.filter(user_id=user_id)]
                response = success_response
            elif module == 'resignation':
                success_response['message'] = [res.obj() for res in Resignation.objects.all()]
                response = success_response

            elif module == 'devices':
                success_response['message'] = [dev.obj() for dev in Device.objects.all()]
                response = success_response

            else:
                raise Exception("Invalid Module")

        elif method == 'PATCH':
            # Handle PATCH requests
            if module == 'employee':
                user_id = data.get('user_id')
                
                area = data.get('area')
                department = data.get('department')
                position = data.get('position')

                Employee.objects.filter(user_id=user_id).update(
                    area=Area.objects.get(pk=area),
                    department=Department.objects.get(pk=department),
                    position=Position.objects.get(pk=position)
                )

                response['status_code'] = 200
                response['message'] = "Employee updated successfully"

            elif module == 'resign':
                user_id = data.get('user_id')
                resign_date = data.get('resign_date')
                resign_type = data.get('resign_type')
                resign_reason = data.get('resign_reason')

                Resignation.objects.create(
                    employee=Employee.objects.get(user_id=user_id),
                    resign_date=resign_date,
                    resign_type=resign_type,
                    resign_reason=resign_reason
                )

                response['status_code'] = 200
                response['message'] = "Employee resigned successfully"

            else:
                raise Exception(f"Invalid Patch Module {module}")

        elif method == 'DELETE':
            # Handle DELETE requests
            pass

        else:
            response['status_code'] = 405
            response['message'] = f"Method {method} not allowed"

    except Exception as e:
        error_type, error_instance, traceback = sys.exc_info()
        tb_path = traceback.tb_frame.f_code.co_filename
        line_number = traceback.tb_lineno
        response["status_code"] = 500
        response["message"] = f"An error of type {error_type} occurred on line {line_number} in file {tb_path}. Details: {str(e)}"
        print(e)

    return JsonResponse(response, safe=False)
