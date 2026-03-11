from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from admin_panel.models import UserAddOns
from .models import Documents
from django.shortcuts import redirect


from iclock.models import Employee,Resignation


@login_required()
def index(request):
    context = {
        'nav': True,
        'page': {
            'title': "Employee",
            'nav':True
        }
    }

    return render(request,'employee/landing.html',context=context)

@login_required()
def area(request):
    context = {
        'nav': True,
        'page': {
            'title': "Area",
            'nav':True
        }
    }

    return render(request,'employee/area.html',context=context)

@login_required()
def departments(request):
    context = {
        'nav': True,
        'page': {
            'title': "Departments",
            'nav':True
        }
    }

    return render(request,'employee/dept.html',context=context)

@login_required()
def employees(request):
    context = {
        'nav': True,
        'page': {
            'title': "Attendance",
            'nav':True
        }
    }

    return render(request,'employee/staff.html',context=context)

@login_required()
def attendance(request):
    context = {
        'nav': True,
        'page': {
            'title': "Employee",
            'nav': True
        }
    }

    return render(request, 'employee/attendance.html', context=context)


@login_required()
def leave(request):
    context = {
        'nav': True,
        'page': {
            'title': "Leave",
            'nav': True
        },
        'my_adon':UserAddOns.objects.get(user=request.user)
    }

    return render(request, 'employee/leave.html', context=context)


def master_leave(request):
    context = {
        'nav': True,
        'page': {
            'title': "Leave",
            'nav': True
        }
    }

    return render(request,'employee/leaves.html',context=context)

@login_required()
def monthly_attendance(request):
    context = {
        'nav': True,
        'page': {
            'title': "Monthly Attendance",
            'nav': True
        }
    }

    return render(request, 'employee/monthly-attendance.html', context=context)

@login_required()
def employee_documents(request):
    context = {
        'nav': True,
        'page': {
            'title': "Employee Documents",
            'nav': True,
            
        },
        'documents':Documents.objects.all()
    }

    return render(request, 'employee/documents.html', context=context)

@login_required

def upload_document(request):
    if request.method == 'POST':
        user = request.user
        compliance_type_id = request.POST.get('compliance_type')
        remarks = request.POST.get('remarks', '')
        document_file = request.FILES.get('document_file')

        if not compliance_type_id or not document_file:
            # Missing required fields
            from django.contrib import messages
            messages.error(request, 'Please fill all required fields and attach a document.')
            return redirect(request.META.get('HTTP_REFERER', '/'))

        try:
            document_type = Documents.objects.get(pk=compliance_type_id)
        except Documents.DoesNotExist:
            from django.contrib import messages
            messages.error(request, 'Invalid compliance type selected.')
            return redirect(request.META.get('HTTP_REFERER', '/'))

        # Save the uploaded document: you may need a model like EmployeeDocument or similar
        from .models import EmployeeDocuments  # Assuming such model exists
        emp_doc = EmployeeDocuments(
            user=user,
            document=document_type,
            remark=remarks,
            status='PENDING',
            file=document_file

        )
        
        emp_doc.save()

        from django.contrib import messages
        messages.success(request, 'Document uploaded successfully.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    # If not POST, show error
    from django.contrib import messages
    messages.error(request, 'Invalid request method.')
    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def self_service(request):
            """
            Employee Self-Service View.
            Shows the employee self-service dashboard or options.
            """
            user = request.user
            # Gather info relevant for self-service; add to context as needed
            context = {
                'user': user,
                # Add additional context variables for dashboard/widgets as needed
            }
            return render(request, 'employee/self_service.html', context)


            # INSERT_YOUR_CODE
@login_required
def my_attendance(request):
    """
    Employee My Attendance View.
    Shows the attendance details specific to the requesting user.
    """
    user = request.user
    

    context = {
        'user': user,
        # Add more context as required for the page/layout.
    }
    return render(request, 'employee/my_attendance.html', context)

    # INSERT_YOUR_CODE
@login_required
def submit_attendance(request):
    """
    Handle employee attendance submission (punch in/out with an image).
    """
    from django.contrib import messages
    from django.shortcuts import redirect
    user = request.user

    if request.method == "POST":
        punch_stage = request.POST.get('punch_stage')
        remarks = request.POST.get('remarks', '')
        image = request.FILES.get('image')

        if not punch_stage or punch_stage not in ['IN', 'OUT']:
            messages.error(request, "Invalid punch stage selected.")
            return redirect(request.META.get('HTTP_REFERER', '/'))

        if not image:
            messages.error(request, "Please upload an image for verification.")
            return redirect(request.META.get('HTTP_REFERER', '/'))

        # Here, you would save the attendance to a model, e.g., Attendance
        # This example assumes you have a model Attendance with fields: user, punch_stage, image, remarks, timestamp

        from django.utils import timezone
        # If Attendance model is in employee.models, import as needed
        try:
            from .models import ManualPunc
            ManualPunc.objects.create(
                employee=user,
                state=punch_stage,
                remarks=remarks,
                selfie=image
            )
            messages.success(request, "Attendance recorded successfully.")
        except Exception as e:
            messages.error(request, f"Failed to record attendance: {e}")
            return redirect(request.META.get('HTTP_REFERER', '/'))

        return redirect('hrm_my_attendance')

    else:
        messages.error(request, "Invalid request method.")
        return redirect(request.META.get('HTTP_REFERER', '/'))


        # INSERT_YOUR_CODE
@login_required
def manual_punch(request):
    """
    Employee My Attendance View.
    Shows the attendance details specific to the requesting user.
    """
    user = request.user
    

    context = {
        'user': user,
        'page':{
            'title':"Manual Punches",
            'nav':True
        },
        'nav':True,
        # Add more context as required for the page/layout.
    }
    return render(request, 'employee/manual_punch.html', context)
@csrf_exempt
def upload_resign_document(request):
    if request.method == 'POST':

        try:
            form = request.POST
            file = request.FILES

            document = file['resign_document']
            user_id = form['user_id']

            employee = Employee.objects.get(user_id=user_id)
            resign = Resignation.objects.get(employee=employee)

            resign.resign_document = document

            resign.save()
            return redirect(request.META.get('HTTP_REFERER', '/'))
        except Exception as e:
            return HttpResponse(f"Error: {e}")

    else:
        return HttpResponse("Invalid request method.")

        

def resigned_employees(request):
    context = {
        'nav': True,
        'page': {
            'title': "Resigned",
            'nav':True
        }
    }

    return render(request,'employee/resigned_employees.html',context=context)


def devices(request):
    context = {
            'nav': True,
            'page': {
                'title': "Devices",
                'nav':True
            }
        }

    return render(request,'employee/devices.html',context=context)


