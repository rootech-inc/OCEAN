from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt

from admin_panel.anton import error_response, success_response
from pm.models import Clients, Projects


@login_required
def index(request):
    context = {
        'nav': True,
        'clients': Clients.objects.all().order_by('name'),
        'type_choices': Projects.type_choices,
        'page': {
            'title': 'Projects',
            'card': False,
        },
    }
    return render(request, 'pm/projects.html', context=context)


@login_required
def clients(request):
    context = {
        'nav': True,
        'page': {
            'title': 'Clients',
            'card': False,
        },
    }
    return render(request, 'pm/clients.html', context=context)


@login_required
def new_project(request):
    context = {
        'nav': True,
        'clients': Clients.objects.all().order_by('name'),
        'type_choices': Projects.type_choices,
        'page': {
            'title': 'New Project',
            'card': False,
        },
    }
    return render(request, 'pm/new_project.html', context=context)


@login_required
def project_detail(request, url):
    project = get_object_or_404(Projects, url=url)
    context = {
        'nav': True,
        'project': project,
        'clients': Clients.objects.all().order_by('name'),
        'type_choices': Projects.type_choices,
        'page': {
            'title': project.title,
            'card': False,
        },
    }
    return render(request, 'pm/project_detail.html', context=context)


@login_required
@csrf_exempt
def upload_client_logo(request):
    if request.method == 'POST':
        pk = request.POST.get('pk')
        logo = request.FILES.get('logo')
        if not pk or not logo:
            return JsonResponse(error_response('Client pk and logo file are required.'))
        client = get_object_or_404(Clients, pk=pk)
        client.logo = logo
        client.save()
        return JsonResponse(success_response(client.obj()))
    return JsonResponse(error_response('Invalid request method'))


@login_required
@csrf_exempt
def upload_project_cover(request):
    if request.method == 'POST':
        pk = request.POST.get('pk')
        cover_image = request.FILES.get('cover_image')
        if not pk or not cover_image:
            return JsonResponse(error_response('Project pk and cover image are required.'))
        project = get_object_or_404(Projects, pk=pk)
        project.cover_image = cover_image
        project.save()
        return JsonResponse(success_response(project.obj()))
    return JsonResponse(error_response('Invalid request method'))
