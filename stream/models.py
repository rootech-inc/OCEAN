import os
from datetime import datetime
from django.db import models
from django.contrib.auth.models import User
import random
import string

# Create your models here.

class Series(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='series', null=True, blank=True)
    key = models.CharField(max_length=32, unique=True, null=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to='static/uploads/series/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        super(Series, self).save(*args, **kwargs)

    def __str__(self):
        return self.title


# Create your models here.
class Videos(models.Model):
    key = models.TextField()
    title = models.TextField()
    descr = models.TextField()
    file = models.FileField(upload_to=f'static/uploads/videos/')
    series = models.ForeignKey(Series, on_delete=models.SET_NULL, null=True, blank=True, related_name='videos')
    episode_number = models.PositiveIntegerField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True, null=True)

    def thumbnail(self):
        file_path = f'/static/general/videos/{self.key}.jpg'
        if os.path.exists(file_path):
            return file_path
        else:
            return '/static/general/videos/img.png'

    views_count = models.IntegerField(default=0)


class Comments(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video = models.ForeignKey(Videos, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.video.title}"


class Views(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    video = models.ForeignKey(Videos, on_delete=models.CASCADE, related_name='views')
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.video.title} - {self.ip}"
