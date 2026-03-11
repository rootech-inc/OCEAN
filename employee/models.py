from django.contrib.auth.models import User
from django.db import models
from datetime import timedelta, datetime
from time import strftime
import calendar


class Attendance(models.Model):
    emp_code = models.CharField(null=False,max_length=100)
    name = models.CharField(max_length=255,null=False)
    date = models.DateField()
    time_in = models.TimeField()
    time_out = models.TimeField(null=True, blank=True)
    time_diff = models.DecimalField(default=0.00,decimal_places=2,max_digits=10)
    status = models.CharField(max_length=20, choices=[
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('half_day', 'Half Day'),
        ('leave', 'Leave')
    ],default='absent')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_late = models.BooleanField(default=True)
    dep_text = models.CharField(null=True,max_length=255)
    
    def is_off(self):
        import calendar
        day = calendar.day_name[datetime.strptime(str(self.date).split(' ')[0], '%Y-%m-%d').weekday()]
        if self.dep_text == "METERS" or self.dep_text == 'MOTORS':
            if day == 'Sunday':
                return True
            else:
                return True
        else:
            return False


    def obj(self):
        import calendar
        return {
            'id': self.id,
            'employee': self.emp_code,
            'date': self.date,
            'time_in': self.time_in,
            'time_out': self.time_out,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'is_late':self.is_late,
            'dept':self.dep_text,
            'name':self.name,
            'dep_text':self.dep_text,
            'day': calendar.day_name[self.date.weekday()]
        }


    def __str__(self):
        return f"{self.emp_code} - {self.date}"

    class Meta:
        db_table = 'attendance'
        ordering = ['-date', '-time_in']
        unique_together = ['emp_code', 'date']



class AttendanceLog(models.Model):
    # The device serial number (e.g., MED7241100432)
    device_sn = models.CharField(max_length=50, db_index=True)
    
    # The employee's PIN/ID on the machine
    user_id = models.CharField(max_length=20, db_index=True)
    
    # The exact time of the punch
    timestamp = models.DateTimeField()
    
    # Punch State: 0=Check-In, 1=Check-Out, 2=Break-Out, 3=Break-In
    PUNCH_CHOICES = [
        (0, 'Check-In'),
        (1, 'Check-Out'),
        (2, 'Break-Out'),
        (3, 'Break-In'),
    ]
    punch_state = models.IntegerField(choices=PUNCH_CHOICES, default=0)
    
    # Verify Type: 15=Face, 1=Fingerprint, 3=Password, 4=Card
    VERIFY_CHOICES = [
        (1, 'Fingerprint'),
        (3, 'Password'),
        (4, 'Card'),
        (15, 'Face'),
        (20, 'Face (SpeedFace)'),
    ]
    verify_type = models.IntegerField(choices=VERIFY_CHOICES, default=0)
    
    # Store extended data if needed (Temperature/Mask)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, default=0.0)
    is_masked = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevents duplicate entries if the device pushes the same log twice
        unique_together = ('device_sn', 'user_id', 'timestamp')
        ordering = ['-timestamp']

    def __str__(self):
        return f"User {self.user_id} - {self.get_punch_state_display()} at {self.timestamp}"

class Leave(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE,null=False)
    
    leave_type = models.CharField(max_length=255,null=False,choices=[
        ('sick', 'Sick'),
        ('casual', 'Casual'),
        ('annual', 'Annual'),
        ('maternity', 'Maternity'),
        ('paternity', 'Paternity'),
        ('marriage', 'Marriage'),
        ('bereavement', 'Bereavement'),
        ('compensatory', 'Compensatory'),
        ('unpaid', 'Unpaid Leave')
    ])

    start_date = models.DateField(null=False)
    end_date = models.DateField(null=False)

    reason = models.TextField(null=False)
    status = models.CharField(max_length=20, choices=[
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending'),
        ('requested', 'Requested'),
        ('overdue', 'Overdue'),
        ('complete', 'Complete')
    ],default='pending')
    date = models.DateField()
    reliever = models.CharField(max_length=255,null=True)
    
    def __str__(self):
        return f"{self.employee} - {self.leave_type} - {self.start_date}"
    
    def number_of_days(self):
        return (self.end_date - self.start_date).days + 1

    def obj(self):
        return {
            'id': self.id,
            "employee":{
                "username":self.employee.username,
                'pk':self.employee.pk,
                'name':self.employee.get_full_name()
            },
            'req_date':self.date,
            'start_date':self.start_date,
            'end_date':self.end_date,
            'days':self.number_of_days(),
            'reason':self.reason,
            'status':self.status,
            'reliever':self.reliever,
            'type':self.leave_type,
        }


class Documents(models.Model):
    enc = models.CharField(max_length=255,null=False,blank=False,unique=True)
    title = models.CharField(max_length=255,null=False,blank=False,unique=True)
    description = models.TextField()
    created_by = models.ForeignKey(User,on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    required = models.BooleanField(default=False)

class EmployeeDocuments(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    document = models.ForeignKey(Documents,on_delete=models.CASCADE)
    file = models.ImageField(upload_to='static/uploads/amc/assets/')
    created_at = models.DateTimeField(auto_now_add=True)
    remark = models.TextField()
    status_type = [
        ('pending',"Pending"),
        ('approved',"Approved"),
        ('rejected',"Rejected")
    ]

    status = models.CharField(max_length=255,choices=status_type,null=False,blank=False,default='pending')

    class Meta:
        unique_together = ('user', 'document')


class ManualPunc(models.Model):
    employee = models.ForeignKey(User,on_delete=models.CASCADE)
    status_choices = [
        ('IN',"Check In"),
        ("OUT","Check Out")
    ]
    state = models.CharField(max_length=255,choices=status_choices,null=False,blank=False)
    remarks = models.TextField()
    selfie = models.ImageField(upload_to='static/uploads/amc/assets/')
    created_at = models.DateTimeField(auto_now_add=True)


    def obj(self):
        return {
            'id': self.id,
            'name':self.employee.get_full_name() if self.employee else 'No Name',
            'position':"Unknown",
            "company":"Unknown",
            'employee': self.employee.id if self.employee else None,
            'status': self.state,
            'remarks': self.remarks,
            'selfie': self.selfie.url if self.selfie else None,
            'created_at': self.created_at,
            'date': self.created_at.date() if self.created_at else None,
            'time': self.created_at.time() if self.created_at else None,
        }
