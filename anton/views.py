from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import *

@login_required
def index(request):
    context = {
        'nav': True,
        'page': {
            'title': "Anton AI"
        }
    }
    return render(request, 'anton/index.html', context=context)

@login_required
def my_models(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        provider = request.POST.get('provider')
        api_key = request.POST.get('api_key')
        
        if name and provider and api_key:
            Agent.objects.create(name=name, provider=provider, api_key=api_key)
            messages.success(request, "Agent added successfully!")
            return redirect('my_models')
        else:
            messages.error(request, "All fields are required.")

    agents = Agent.objects.all().order_by('-created_at')
    context = {
        'nav': True,
        'page': {
            'title': "My AI Models"
        },
        'agents': agents
    }
    return render(request, 'anton/my_models.html', context=context)
