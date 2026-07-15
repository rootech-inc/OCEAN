import uuid
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse

from django.shortcuts import render, redirect
from django.utils.formats import number_format
from django.views.decorators.csrf import csrf_exempt

from admin_panel.anton import shorten_url, make_md5_hash
from admin_panel.models import Sms, SmsApi, MailQueues, MailSenders
from appconfig.form import NewApp, NewVersion
from appscenter.models import AppsGroup, App, AppAssign, AppProviders, Subscribers
from blog.anton import make_md5
from ocean import settings
from ocean.settings import BASE_URL


@login_required()
def index(request):
    import time

    username = request.user.username
    current_time = str(time.time())
    data = username + current_time
    provider_options = ''
    providers = AppProviders.objects.filter(is_active=True)
    for provider in providers:
        provider_options += f"<option value='{provider.pk}'>{provider.name}</option>"


    context = {
        'nav': True,
        'providers': AppProviders.objects.filter(is_active=True),
        'apps': App.objects.all(),
        'md': make_md5(data),
        'html':{
            'providers_options': provider_options
        }
    }

    return render(request, 'appcenter/index.html', context=context)


@login_required()
@csrf_exempt
def save_new_app(request):
    if request.method == 'POST':
        form = NewApp(request.POST, request.FILES)
        try:

            form.save()
            messages.success(request, "APP SAVED")
        except Exception as e:
            messages.error(request, e)
            return HttpResponse(form)

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@login_required()
def app(request, uni):
    this_app = App.objects.get(uni=uni)
    assign = AppAssign.objects.filter(app=this_app)
    versions = this_app.versioncontrol_set.all().order_by('-version_no')
    subscribers = Subscribers.objects.filter(app=this_app)

    context = {
        'nav': True,
        'app': this_app,
        'next_version': number_format(this_app.version + Decimal(0.2),1),
        'assigns': assign,
        'versions': versions,
        'subscribers': subscribers
    }
    return render(request, 'appcenter/app.html', context=context)


@login_required()
def save_app_update(request):
    # return HttpResponse("HELLo WORLD")
    if request.method == 'POST':
        form = NewVersion(request.POST, request.FILES)

        try:
            form.save()
            version = form.cleaned_data['version_no']
            description = form.cleaned_data['description']
            
            appx = App.objects.get(pk=form.cleaned_data['app'].pk)
            lastest_url = appx.lastest_url()
            app_name = appx.name
            ap = appx
            appx.version = version
            appx.save()
            msg = (f"Software Update \n\nThere is a new update for {app_name}, Please apply update or contact provider. If "
                   f"issue persists after the update, please inform IT Department 054 631 00 11")

            CUST_URL = settings.BASE_URL
            if CUST_URL.endswith('/'):
                CUST_URL = CUST_URL[:-1]


            email_template = f"""
            <!DOCTYPE html>
            <html>
            <head>
              <meta charset="UTF-8">
              <meta name="viewport" content="width=device-width, initial-scale=1.0">
              <style>
                body {{
                  font-family: 'Segoe UI', Arial, sans-serif;
                  background-color: #f4f4f4;
                  margin: 0;
                  padding: 0;
                }}
                .container {{
                  max-width: 600px;
                  margin: 20px auto;
                  background: #ffffff;
                  border-radius: 8px;
                  overflow: hidden;
                  border: 1px solid #e0e0e0;
                }}
                .header {{
                  background-color: #1A6B3C;
                  color: #ffffff;
                  padding: 20px 30px;
                  text-align: center;
                }}
                .header h2 {{
                  margin: 0;
                  font-weight: 500;
                }}
                .body {{
                  padding: 30px;
                  color: #333333;
                  line-height: 1.6;
                  font-size: 15px;
                }}
                .changelog {{
                  background-color: #f9f9f9;
                  border-left: 4px solid #E8521A;
                  padding: 15px 20px;
                  margin-top: 15px;
                  border-radius: 4px;
                }}
                .changelog h3, .changelog h4 {{
                  margin-top: 0;
                  color: #1A6B3C;
                }}
                .changelog ul {{
                  padding-left: 20px;
                  margin: 8px 0;
                }}
                .footer {{
                  padding: 15px 30px;
                  font-size: 12px;
                  color: #999999;
                  text-align: center;
                  border-top: 1px solid #eeeeee;
                }}
                .btn {{
                  display: inline-block;
                  margin-top: 20px;
                  padding: 10px 20px;
                  background-color: #E8521A;
                  color: #ffffff !important;
                  text-decoration: none;
                  border-radius: 5px;
                  font-weight: 500;
                }}
              </style>
            </head>
            <body>
              <div class="container">
                <div class="header">
                  <h2>Software Update</h2>
                </div>
                <div class="body">
                  <p>There is a new update available for <strong>{app_name}</strong>.</p>
                  <div class="changelog">
                    {description}
                  </div>
                  <p>Please apply the update as soon as possible. If the issue persists after updating, contact the IT Department at <strong>054 631 00 11</strong>.</p>
                  <a href="{CUST_URL}{lastest_url}" class="btn">Download Update</a>
                </div>
                <div class="footer">
                  &copy; {app_name}. All rights reserved.
                </div>
              </div>
            </body>
            </html>
            """

            # get all users with this app
            app_assign = Subscribers.objects.filter(app=ap)
            for sub in app_assign:
                Sms(api=SmsApi.objects.get(is_default=True),to = sub.phone,message = msg).save()
                MailQueues.objects.create(
                    sender=MailSenders.objects.get(is_default=True),
                    recipient=sub.email,
                    subject=f"Update for {app_name}",
                    body=f"{email_template}",
                    mail_key=make_md5_hash(make_md5_hash(uuid.uuid4())),
                )

            # return HttpResponse("DONE")
            # alert users
            messages.success(request, "VERSION SAVED")
        except Exception as e:
            # return HttpResponse(e)
            messages.error(request, e)
            return HttpResponse(str(e))

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
