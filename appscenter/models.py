from datetime import datetime

from django.contrib.auth.models import User
from django.db import models

from admin_panel.anton import generate_text
from inventory.models import Computer, ComputerGroup
from ocean import settings


# app providers
class AppProviders(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    email = models.EmailField()
    phone = models.TextField()
    country = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)


# APPS GROUPS
class AppsGroup(models.Model):
    name = models.TextField()
    uni = models.CharField(max_length=60, unique=True)

    created_date = models.DateField(auto_now_add=True)
    created_time = models.TimeField(auto_now=True)
    status = models.IntegerField(default=1)


class App(models.Model):
    provider = models.ForeignKey(AppProviders, on_delete=models.CASCADE, default=1, blank=False, null=False)
    logo = models.ImageField(upload_to='static/uploads/apps/logos/', blank=True, null=True,default='static/apps/logos/default'
                                                                                           '.png')
    name = models.TextField()
    uni = models.CharField(max_length=60, unique=True)
    description = models.TextField()
    file = models.FileField(upload_to=f"static/uploads/apps/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}")
    root = models.TextField()

    created_date = models.DateField(auto_now_add=True)
    created_time = models.TimeField(auto_now=True)
    status = models.IntegerField(default=1)
    version = models.DecimalField(default=0.0, decimal_places=1, max_digits=5)

    def latest_version(self):
        return VersionControl.objects.filter(app=self).order_by('-pk')[:1]

    def lastest_url(self):
        if VersionControl.objects.filter(app=self).exists():
            file = VersionControl.objects.filter(app=self).last()
            return file.files.url
        else:
            return '#'

    def prov(self):
        if self.provider == 'null':
            return False
        else:
            return True

    def changelog(self):
        version_list = {}
        for version in VersionControl.objects.filter(app=self).order_by('-pk'):
            version_list[version.version_no] = {
                "description": version.description,
                "date": version.created_date,
                "time": version.created_time,
            }

        agent_comment = f"""You are a technical writer generating a changelog for internal/customer use.

        Below is the raw version data (JSON):
        {version_list}
    
        Instructions:
        - Output ONLY the changelog in Markdown format. No preamble, no explanation, no "next steps" section, no meta-commentary.
        - Use this exact structure for each version, ordered from newest to oldest:
    
        ## [version_no] - date
        _time_
    
        - description (rewritten as a clear, user-facing bullet point if it reads like a raw commit note; otherwise use as-is)
    
        - Do NOT invent, assume, or pad any feature details that aren't present in the description field.
        - Do NOT use placeholders like "xx" — if a description is empty or unclear, just omit that entry or list it verbatim, don't ask me to fill it in.
        - Do NOT include a "How to interpret this changelog" section or any instructional text aimed at me.
        - If there are multiple versions, group them under a single "# Changelog" heading at the top, each version as its own subsection.
    
        Return raw Markdown text only."""

        return generate_text(agent_comment)

    def obj(self):
        app = self
        return {
            'name': app.name,
            'pk': app.pk,
            'uni': app.uni,
            'description': app.description,
            'version': app.version,
            'latest': app.lastest_url(),
            'changelog': "",
            'subscribers':[sub.obj() for sub in Subscribers.objects.filter(app=self)]
        }


class VersionControl(models.Model):
    app = models.ForeignKey('App', on_delete=models.CASCADE)
    description = models.TextField()
    version_no = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    files = models.FileField(upload_to=f"static/uploads/appversion")

    created_date = models.DateField(auto_now_add=True)
    created_time = models.TimeField(auto_now=True)
    status = models.IntegerField(default=1)


class AppAssign(models.Model):
    app = models.ForeignKey('App', on_delete=models.CASCADE)
    mach = models.ForeignKey(Computer, on_delete=models.CASCADE)
    version = models.IntegerField(default=0)

    created_date = models.DateField(auto_now_add=True)
    created_time = models.TimeField(auto_now_add=True)
    updated_date = models.DateField(auto_now_add=True)
    updated_time = models.TimeField(auto_now_add=True)

    message = models.TextField(default='NULL')
    last_breath = models.TextField(default='NULL')


class AppContainer(models.Model):
    name = models.CharField(max_length=255)
    computers = models.ManyToManyField(ComputerGroup)

    def __str__(self):
        return self.name


class ErrorLogs(models.Model):
    app = models.ForeignKey('App', on_delete=models.CASCADE)
    title = models.CharField(max_length=255,null=False,unique=False,blank=False)
    message = models.TextField()

    created_date = models.DateField(auto_now_add=True)
    created_time = models.TimeField(auto_now=True)

    is_assigned = models.BooleanField(default=False)
    assigned_to = models.ForeignKey(User,on_delete=models.CASCADE)

class Subscribers(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=255)
    app = models.ForeignKey('App', on_delete=models.CASCADE)

    def obj(self):
        return {
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
        }

    class Meta:
        unique_together = (('app', 'email'),('app', 'phone'),)