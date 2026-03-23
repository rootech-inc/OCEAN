from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Device, Employee, AttendanceLog, RawAttendance
from django.utils import timezone
from datetime import timedelta
import re
from django.utils.dateparse import parse_datetime



def next_cmd_id(device):
    device.last_cmd_id = (device.last_cmd_id or 200) + 1
    device.save(update_fields=['last_cmd_id'])
    return device.last_cmd_id

def should_sync_users(sn):
    device, _ = Device.objects.get_or_create(serial_number=sn)
    if not device.last_user_sync or device.last_user_sync < timezone.now() - timedelta(hours=24):
        return True
    return False

def should_sync_logs(sn):
    device, _ = Device.objects.get_or_create(serial_number=sn)
    if not device.last_log_sync or device.last_log_sync < timezone.now() - timedelta(hours=1):
        return True
    return False

@csrf_exempt
def handle_cdata(request):
    sn = request.GET.get('SN')
    table = request.GET.get('table')
    device_obj, _ = Device.objects.get_or_create(serial_number=sn)

    if request.method == 'POST':
        raw_data = request.body.decode('utf-8')
        lines = raw_data.strip().split('\n')

        if table == 'user':
            for line in lines:
                if not line.strip():
                    continue
                fields = line.split('\t')
                if len(fields) >= 2:
                    Employee.objects.update_or_create(
                        user_id=fields[0].strip(),
                        defaults={'name': fields[1].strip()}
                    )
            device_obj.last_user_sync = timezone.now()
            device_obj.save()
            print(f"[{sn}] Synced {len(lines)} users")

        elif table == 'ATTLOG':
            saved = 0
            for line in lines:
                if not line.strip():
                    continue
                fields = line.split('\t')
                try:
                    u_id     = fields[0].strip()
                    naive_dt = parse_datetime(fields[1].strip())
                    t_stamp = timezone.make_aware(naive_dt, timezone.get_current_timezone())
                    p_state  = int(fields[2])
                    v_type   = int(fields[3])
                    temp     = float(fields[7]) if len(fields) > 7 else 0.0

                    employee = Employee.objects.filter(user_id=u_id).first()

                    if employee is None:
                        print(f"[{sn}] Skipping punch for unknown user_id={u_id} — not in Employee table yet")
                        continue

                    att_date = t_stamp.date()
                    
                    AttendanceLog.objects.update_or_create(
                        device_sn=sn,
                        device=device_obj,
                        user_id=u_id,
                        timestamp=t_stamp,
                        defaults={
                            'device': device_obj,
                            'employee': employee,
                            'punch_state': p_state,
                            'verify_type': v_type,
                            'temperature': temp,
                        }
                    )

                    raw, created = RawAttendance.objects.get_or_create(
                        employee=employee,
                        day=att_date,
                        defaults={
                            'first_punch': t_stamp.time(),
                            'last_punch': t_stamp.time(),
                        }
                    )

                    if not created:
                        update_fields = []
                        if t_stamp.time() < raw.first_punch:
                            raw.first_punch = t_stamp.time()
                            update_fields.append('first_punch')
                        if t_stamp.time() > raw.last_punch:
                            raw.last_punch = t_stamp.time()
                            update_fields.append('last_punch')
                        if update_fields:
                            raw.save(update_fields=update_fields)
                    saved += 1
                except (IndexError, ValueError) as e:
                    print(f"[{sn}] Skipping bad ATTLOG line: {line!r} — {e}")
                    continue

            device_obj.last_log_sync = timezone.now()
            device_obj.save()
            print(f"[{sn}] Saved {saved} attendance records")

        return HttpResponse("OK", content_type="text/plain")

    return HttpResponse("OK", content_type="text/plain")

@csrf_exempt
def handle_heartbeat(request):
    sn = request.GET.get('SN')
    device, _ = Device.objects.get_or_create(serial_number=sn)

    info = request.GET.get('INFO', '')
    if info:
        parts = info.split(',')
        if len(parts) >= 5:
            device.ip_address = parts[4]
            device.save()

    # Priority 1: user sync (must happen before log sync
    # so employees exist before punches arrive)
    if device.needs_backfill and device.backfill_from:
        cmd_id = next_cmd_id(device)
        start_time = device.backfill_from.strftime("%Y-%m-%d %H:%M:%S")
        cmd = f"C:{cmd_id}:DATA QUERY ATTLOG StartTime:{start_time}"
        print(f"[{sn}] Backfill from {start_time}: {cmd}")
        # Clear the flag so it only runs once
        device.needs_backfill = False
        device.backfill_from = None
        device.save(update_fields=['needs_backfill', 'backfill_from'])
        return HttpResponse(cmd, content_type="text/plain")

    if should_sync_users(sn):
        cmd_id = next_cmd_id(device)
        cmd = f"C:{cmd_id}:DATA QUERY USERINFO StartTime:0000-00-00 00:00:00"
        print(f"[{sn}] Requesting user sync: {cmd}")
        device.last_user_sync = timezone.now()
        device.save()
        return HttpResponse(cmd, content_type="text/plain")

    # Priority 2: log sync (only runs if no user sync needed)
    if should_sync_logs(sn):
        cmd_id = next_cmd_id(device)

        if device.last_log_sync:
            start_time = device.last_log_sync.strftime("%Y-%m-%d %H:%M:%S")
        else:
            start_time = (timezone.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

        cmd = f"C:{cmd_id}:DATA QUERY ATTLOG StartTime:{start_time}"
        print(f"[{sn}] Sending log sync: {cmd}")
        return HttpResponse(cmd, content_type="text/plain")

    return HttpResponse("OK", content_type="text/plain")
@csrf_exempt
def handle_device_command(request):
    """Device POSTs the result of a command back here."""
    if request.method == 'POST':
        sn = request.GET.get('SN')
        raw_response = request.body.decode('utf-8')
        print(f"[{sn}] Command result: {raw_response}")

        # Parse return code for debugging
        match = re.search(r'Return=(-?\d+)', raw_response)
        if match:
            code = int(match.group(1))
            if code == 0:
                print(f"[{sn}] ✓ Command succeeded")
            else:
                # Common codes:
                # -1: General error
                # -1004: Invalid command / not supported
                # -2: Device busy
                print(f"[{sn}] ✗ Command failed with code {code}")

        return HttpResponse("OK", content_type="text/plain")

    return HttpResponse("OK", content_type="text/plain")


@csrf_exempt
def handle_ping(request):
    return HttpResponse("OK", content_type="text/plain")