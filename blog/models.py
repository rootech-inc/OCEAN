from datetime import datetime

from django.contrib.auth.models import User
from django.db import models
import os



# Create your models here.
class articles(models.Model):
    uni = models.CharField(max_length=200, unique=True)
    author = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    status = models.IntegerField(default=0)
    article = models.TextField()
    title = models.CharField(max_length=200)
    tag = models.CharField(max_length=200)
    intro = models.TextField(default='none')
    meta = models.CharField(max_length=200, default='none')
    image = models.ImageField(upload_to=f'static/uploads/articles',
                              default='static/general/img/articles/def_img.png')
    thumbnail = models.ImageField(upload_to=f'static/uploads/articles',
                                  default='static/general/img/articles/def_thumb.png')

    date_created = models.DateField(auto_now_add=True)
    time_created = models.TimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    

    scope_type = (
        ('public','Public'),
        ('private','Private'),
        ('protected','Protected'),
    )

    scope = models.CharField(max_length=200, choices=scope_type, default='public')

    def author_dp(self):
        if self.author:
            from admin_panel.models import UserAddOns
            if UserAddOns.objects.filter(user=self.author).exists():
                addOn = UserAddOns.objects.get(user=self.author)
                return addOn.dp_url()
            else:
                return "static/general/img/articles/def_img.png"
        return ""

    def image_url(self):
        # check if file exist
        if os.path.exists(self.image.path):
            return self.image.url
        return ""

    def thumbnail_url(self):
        if os.path.exists(self.thumbnail.path):
            return self.thumbnail.url
        return ""

    def obj(self):
        return {
            'uni': self.uni,
            'author': self.author.username,
            'status': self.status,
            'article': self.article,
            'title': f"{self.author.get_full_name() if self.author else 'anonymous'} - {self.title}",
            'tag': self.tag,
            'intro': self.intro,
            'meta': self.meta,
            'image': self.image_url(),
            'thumbnail': self.thumbnail_url(),
            'date_created': self.date_created,
            'time_created': self.time_created,
            'updated_at': self.updated_at,
            'scope': self.scope,
            'author_dp': self.author_dp(),
        }


class article_meta(models.Model):
    id = models.IntegerField(primary_key=True)
    description = models.TextField()
    status = models.IntegerField(default=1)
    created_at = models.TextField()
    updated_at = models.TextField()
    owner = models.CharField(max_length=200, default='anton')

    def __str__(self):
        return str(self.description)


class userAccounts(models.Model):
    username = models.TextField(max_length=1000)
    token = models.TextField(max_length=1000)
    meta_words = models.TextField(max_length=1000)

    def __str__(self):
        return str(self.token)


class ArticleView(models.Model):
    article = models.TextField()
    user = models.IntegerField(default=0)


class Notofication(models.Model):
    sent_from = models.IntegerField(default=0)
    sent_to = models.IntegerField(default=0)
    title = models.TextField()
    message = models.TextField()
    sent_on = models.DateTimeField(auto_now_add=True)
    read = models.IntegerField(default=0)


class Providers(models.Model):
    provider_code = models.CharField(max_length=3)
    descr = models.TextField()
    mobile = models.TextField()
    email = models.TextField()


class ArticleChat(models.Model):
    article = models.IntegerField()
    sent_from = models.IntegerField()
    message = models.TextField()
    sent_on = models.DateTimeField(auto_now=True)

    def owner_name(self):
        return User.objects.get(pk=self.sent_from)
