from django.db import models

# Create your models here.
class Alarms(models.Model):
    domain = models.CharField(max_length=255,null=False)
    alarm_type = models.CharField(max_length=255,null=False)
    title = models.CharField(max_length=255,null=False)
    description = models.CharField(max_length=255,null=False)
    date_added = models.DateField(null=False,blank=False)


    def obj(self):
        return {
            'domain':self.domain,
            'alarm_type':self.alarm_type,
            'title':self.title,
            'description':self.description,
            'date_added':self.date_added,
        }
