import PIL.ImageChops
from django.db import models
from django.utils import timezone

class Area(models.Model):
    area_code = models.CharField(max_length=20, unique=True)
    area_name = models.CharField(max_length=150, blank=False, null=False,unique=True)
    work_start_time = models.TimeField()
    work_end_time = models.TimeField()
    how_many_off_days = models.IntegerField(default=1)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.area_code} - {self.area_name}"

    def attendance_summary(self, work_date=None):
        if work_date is None:
            work_date = timezone.now().date()
        
        total_workers = Employee.objects.filter(area=self,is_resigned=False).count()
        
        # Count distinct employees who have at least one punch on work_date
        present = AttendanceLog.objects.filter(
            employee__area=self,
            timestamp__date=work_date
        ).values('user_id').distinct().count()  # ← distinct per employee
        
        absent = total_workers - present
        attendance_percentage = round((present / total_workers) * 100, 2) if total_workers > 0 else 0

        return {
            'area': self.area_name,
            'work_date': work_date,
            'total_workers': total_workers,
            'present': present,
            'absent': absent,
            'attendance_percentage': attendance_percentage,
        }



        return {
            'name':name,
            'workers':total_workers,
            'present':present,
            'abscent':abscent,
            'attendnace_percentage':attendance_percentage
        }

    def obj(self):
        return {
            'area_code': self.area_code,
            'area_name': self.area_name,
            'pk': self.pk,
            'work_start_time':self.work_start_time,
            'work_end_time':self.work_end_time,
            'days_of_work':self.how_many_off_days,
            'is_default':self.is_default
        }

class Department(models.Model):
    dept_code = models.CharField(max_length=20, unique=True)
    dept_name = models.CharField(max_length=150, blank=False, null=False,unique=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.dept_code} - {self.dept_name}"

    def obj(self):
        return {
            'dept_code': self.dept_code,
            'dept_name': self.dept_name,
            'pk': self.pk
        }

class Position(models.Model):
    position_code = models.CharField(max_length=20, unique=True)
    position_name = models.CharField(max_length=150, blank=True, null=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.position_code} - {self.position_name}"

    def obj(self):
        return {
            'position_code': self.position_code,
            'position_name': self.position_name,
            'pk': self.pk
        }

# Create your models here.
class Device(models.Model):
    device_area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True, blank=True)
    serial_number = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100, blank=True)
    last_user_sync = models.DateTimeField(null=True, blank=True)
    last_log_sync = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.serial_number})"

    def obj(self):
        return {
            'area':self.device_area.area_name if self.device_area else 'Unknown',
            'serial_no':self.serial_number,
            'name':self.name,
            'last_user_sync':self.last_user_sync,
            'last_log':self.last_log_sync,
            'ip_address':self.ip_address
        }

class Employee(models.Model):
    
    area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True)

    user_id = models.CharField(max_length=20, unique=True, db_index=True)
    
    # The Name as it appears on the machine
    name = models.CharField(max_length=150, blank=True, null=True)
    
    # Metadata for tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_resigned = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Biometric Employee"
        verbose_name_plural = "Biometric Employees"
        ordering = ['user_id']



    def attd_logs(self, work_date=None):
        if work_date is None:
            work_date = timezone.now().date()
        
            log = AttendanceLog.objects.filter(
                employee=self, 
                timestamp__date=work_date
            ).order_by('timestamp').first()  # ← just first log of the day
            
            if not log:
                return None
                
            return {
                'user_id': self.user_id,
                'name': self.name,
                'log': log.obj()
            }  

    def obj(self):
        return {
            'user_id': self.user_id,
            'name': self.name,
            'department': self.department.dept_name if self.department else None,
            'position': self.position.position_name if self.position else None,
            'area': self.area.area_name if self.area else None
        }
class AttendanceLog(models.Model):
    device = models.ForeignKey(
        Device, 
        on_delete=models.CASCADE, 
        to_field='serial_number', 
        related_name='attendance_logs',
        null=True, 
        blank=True
    )
    # Link to Employee: If employee is deleted, logs remain (null=True) 
    # but we use 'to_field' to link specifically to the 'user_id' string
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        to_field='user_id', 
        related_name='logs',
        null=True,
        blank=True
    )
    
    # We keep a copy of the raw user_id in case the employee isn't synced yet
    user_id = models.CharField(max_length=20) 
    device_sn = models.CharField(max_length=50)
    timestamp = models.DateTimeField()
    
    punch_state = models.IntegerField(default=0) # 0: In, 1: Out
    verify_type = models.IntegerField(default=0) # 15: Face, 1: Finger
    temperature = models.DecimalField(max_digits=4, decimal_places=1, default=0.0)

    class Meta:
        unique_together = ('device_sn', 'user_id', 'timestamp')
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user_id} at {self.timestamp}"

    def obj(self):
        return {
            'user_id': self.user_id,
            'device_sn': self.device_sn,
            'timestamp': self.timestamp,
            'punch_state': self.punch_state,
            'verify_type': self.verify_type,
            'temperature': self.temperature,
        }


class Resignation(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,null=False,blank=False)
    resign_date = models.DateField()
    resign_choices = (
        ('0','Resigned'),
        ('1','Terminated'),
        ('2','Retired'),
        ('3','Other')
    )
    resign_type = models.CharField(max_length=10,choices=resign_choices)
    resign_reason = models.CharField(max_length=200)
    resign_document = models.FileField(upload_to='static/resignation_documents/', null=True, blank=True)

    def __str__(self):
        return f"{self.employee.name} - {self.resign_date}"

    def save(self, *args, **kwargs):
        self.employee.is_resigned = True
        self.employee.save()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.employee.is_resigned = False
        self.employee.save()
        super().delete(*args, **kwargs)

    def get_resign_type(self):
        return dict(self.resign_choices)[self.resign_type]

    def days_since_resigned(self):
        return (timezone.now().date() - self.resign_date).days

    def obj(self):
        return {
            'employee':{
                'name':self.employee.name,
                'user_id':self.employee.user_id,
                'department':self.employee.department.dept_name if self.employee.department else None,
                'position':self.employee.position.position_name if self.employee.position else None,
                'area':self.employee.area.area_name if self.employee.area else None
            },
            'resign_date': self.resign_date,
            'resign_type': self.get_resign_type(),
            'resign_reason': self.resign_reason,
            'resign_document': self.resign_document.url if self.resign_document else None,
            'days_since_resigned': self.days_since_resigned(),
        }