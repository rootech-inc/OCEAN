from django.http.response import HttpResponse
from django.shortcuts import render
from .models import *
from django.contrib.auth.decorators import login_required, permission_required

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

