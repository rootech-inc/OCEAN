import os.path

from django.contrib.auth.models import User
from django.db import models


class Clients(models.Model):
    name = models.CharField(max_length=100, unique=True, null=False, blank=False)
    email = models.CharField(max_length=100, unique=True, null=False, blank=False)
    phone = models.CharField(max_length=100, unique=True, null=False, blank=False)
    address = models.TextField()
    logo = models.ImageField(upload_to='static/pm/clients/', null=True, blank=True)

    date_created = models.DateTimeField(auto_now_add=True)

    def obj(self):
        return {
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'date_created': self.date_created,
            'pk': self.pk,
            'logo': self.log_url(),
            'project_count': self.projects_set.count(),
        }

    def log_url(self):
        if self.logo:
            return self.logo.url if os.path.exists(self.logo.path) else None
        else:
            return ''


class Projects(models.Model):
    type_choices = (
        ('infrastructure', 'Infrastructure'),
        ('networking', 'Networking'),
        ('software', 'Software'),
        ('security', 'Security'),
        ('development', 'Development'),
    )
    type = models.CharField(max_length=100, unique=False, null=False, blank=False, choices=type_choices)
    client = models.ForeignKey(Clients, on_delete=models.PROTECT, null=False, blank=False)
    title = models.CharField(max_length=255, null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    url = models.CharField(max_length=255, null=False, blank=False, unique=True)

    seo_description = models.TextField(null=False, blank=False)
    seo_keywords = models.TextField(null=False, blank=False)
    cover_image = models.ImageField(upload_to='static/pm/project_images/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, null=False, blank=False)
    is_open = models.BooleanField(default=True)
    is_closed = models.BooleanField(default=False)

    def cover_url(self):
        if self.cover_image:
            return self.cover_image.url if os.path.exists(self.cover_image.path) else None
        return None

    def obj(self):
        return {
            'pk': self.pk,
            'title': self.title,
            'description': self.description,
            'type': self.type,
            'client': self.client.obj(),
            'seo_description': self.seo_description,
            'seo_keywords': self.seo_keywords,
            'cover_image': self.cover_url(),
            'created_at': self.created_at,
            'created_by': self.created_by.get_full_name() or self.created_by.username,
            'is_open': self.is_open,
            'is_closed': self.is_closed,
            'url': self.url,
            'timeline': [
                tl.obj() for tl in ProjectTimeline.objects.filter(project=self).order_by('-date', '-created_at')
            ],
        }


class ProjectTimeline(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.PROTECT, null=False, blank=False)
    title = models.CharField(max_length=255, null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    date = models.DateField(null=False)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, null=False, blank=False)

    def obj(self):
        return {
            'pk': self.pk,
            'project_pk': self.project_id,
            'title': self.title,
            'description': self.description,
            'date': self.date,
            'created_at': self.created_at,
            'created_by': self.created_by.get_full_name() or self.created_by.username,
        }
