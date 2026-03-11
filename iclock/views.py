from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Device, Employee, AttendanceLog
from django.utils import timezone
from datetime import timedelta
import re
from django.utils.dateparse import parse_datetime

# --- Command ID counter (in-memory, simple incrementing) ---
_cmd_id_counter = 200

def next_cmd_id():
    global _cmd_id_counter
    _cmd_id_counter += 1
    return _cmd_id_counter

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
                    
                    AttendanceLog.objects.update_or_create(
                        device_sn=sn,
                        device=device_obj,
                        user_id=u_id,
                        timestamp=t_stamp,
                        defaults={
                            'device': device_obj,
                            'employee': Employee.objects.filter(user_id=u_id).first(),
                            'punch_state': p_state,
                            'verify_type': v_type,
                            'temperature': temp,
                        }
                    )
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
    device, _ = Device.objects.get_or_create(serial_number=sn)  # ← assign here always

    info = request.GET.get('INFO', '')
    if info:
        parts = info.split(',')
        if len(parts) >= 5:
            device.ip_address = parts[4]
            device.save()

    if should_sync_users(sn):
        device.last_user_sync = timezone.now()
        device.save()

    if should_sync_logs(sn):
        cmd_id = next_cmd_id()
        
        # If never synced, go back 30 days
        # If last synced 3 days ago, start from there
        if device.last_log_sync:
            start_time = device.last_log_sync.strftime("%Y-%m-%d %H:%M:%S")
        else:
            start_time = (timezone.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

        cmd = f"C:{cmd_id}:DATA QUERY ATTLOG StartTime:{start_time}"
        print(f"[{sn}] Sending: {cmd}")
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