import os
import random
import string
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.sites import requests
from django.core.mail import send_mail
from stream.models import *

# Create your views here.
from django.http import HttpResponse
from django.shortcuts import render, redirect


def index(request):
    videos = Videos.objects.all().order_by('-id')
    
    # Sidebar: Only show user's series if logged in
    series_list = []
    if request.user.is_authenticated:
        series_list = Series.objects.filter(owner=request.user).order_by('-created_at')
        
    # Main Content: Show all series (or could be featured/recent)
    all_series = Series.objects.all().order_by('-created_at')
    
    context = {
        'videos': videos,
        'series_list': series_list, # For sidebar
        'all_series': all_series,   # For main content
        'nav': False,

    }
    return render(request, 'streams/index.html', context=context)

@user_passes_test(lambda u: u.is_superuser)
def create_series(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        descr = request.POST.get('description')
        thumbnail = request.FILES.get('thumbnail')
        
        # Key generation is handled in model save method now
        Series.objects.create(title=title, description=descr, thumbnail=thumbnail, owner=request.user)
        return redirect('index')
    return redirect('index')

def view_series(request, key):
    if Series.objects.filter(key=key).exists():
        series = Series.objects.get(key=key)
        videos = series.videos.all().order_by('episode_number', 'uploaded_at') # Order by episode then time
        
        series_list = []
        if request.user.is_authenticated:
            series_list = Series.objects.filter(owner=request.user).order_by('-created_at')
        
        all_series = Series.objects.all().order_by('-created_at')
        
        context = {
            'series': series,
            'videos': videos,
            'series_list': series_list,
            'all_series': all_series,
            'nav': False 
        }
        return render(request, 'streams/series_detail.html', context=context)
    else:
        return redirect('index')


@user_passes_test(lambda u: u.is_superuser)
def upload_video(request):
    current_user = request.user
    if request.method == 'POST':
        form_date = request.POST
        file = request.FILES
        title = form_date['title']
        description = form_date['description']
        video_file = file['video_file']
        custom_thumbnail = file.get('thumbnail')
        series_id = form_date.get('series_id') # Handle series selection

        file_key = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        
        series = None
        if series_id:
             try:
                 series = Series.objects.get(id=series_id)
             except Series.DoesNotExist:
                 pass

        try:
            # Create video object
            video = Videos(
                key=file_key, 
                file=video_file, 
                title=title, 
                descr=description, 
                series=series,
                custom_thumbnail=custom_thumbnail
            )
            video.save()
            
            return HttpResponse("done%%")
        except Exception as e:
            return HttpResponse(f"Could Not Add {e} {video_file}")
    
    # Handle GET or non-POST? 
    # Current implementation only handles POST and returns HttpResponse.
    # The modal issues a POST via fetch.
    return redirect('index')


def watch(request, key):
    if Videos.objects.filter(key=key).exists():
        video = Videos.objects.get(key=key)
        series_videos = None
        if video.series:
             series_videos = video.series.videos.all().order_by('episode_number', 'uploaded_at')
        
        series_list = []
        if request.user.is_authenticated:
            series_list = Series.objects.filter(owner=request.user).order_by('-created_at')
        
        all_series = Series.objects.all().order_by('-created_at')
        
    context = {
            'video': video,
            'series_videos': series_videos,
            'series_list': series_list,
            'all_series': all_series,
            'nav':False
        }
    return render(request, 'streams/watch.html', context=context)


@login_required
def update_series_thumbnail(request, key):
    if request.method == 'POST':
        series = Series.objects.get(key=key)
        if request.user == series.owner or request.user.is_superuser:
            thumbnail = request.FILES.get('thumbnail')
            if thumbnail:
                series.thumbnail = thumbnail
                series.save()
        return redirect('view_series', key=key)
    return redirect('index')


@login_required
def update_video_thumbnail(request, key):
    if request.method == 'POST':
        video = Videos.objects.get(key=key)
        # Check ownership via series owner or if video owner field existed (it doesn't directly, but series does)
        # Assuming for now only superusers or series owners can edit. 
        # But wait, Videos doesn't have an owner field directly. 
        # It has a series, which has an owner. 
        # If video is not in a series, only superuser can edit?
        # User said "as long as am the woener of the series and also vide"
        # Since Video doesn't have owner, let's assume we need to check series owner if series exists, or superuser.
        
        is_owner = False
        if request.user.is_superuser:
            is_owner = True
        elif video.series and video.series.owner == request.user:
            is_owner = True
            
        if is_owner:
            custom_thumbnail = request.FILES.get('thumbnail')
            if custom_thumbnail:
                video.custom_thumbnail = custom_thumbnail
                video.save()
                
        return redirect('watch', key=key)
    return redirect('index')
