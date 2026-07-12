import json

from django.apps.registry import Apps
from django.contrib.auth.models import User
from django.db.models import Model
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from admin_panel.anton import make_md5_hash
from admin_panel.models import Sms, SmsApi, MailQueues, MailSenders
from appscenter.models import AppProviders, App, Subscribers


@csrf_exempt
def interface(request):
    method = request.method
    response = {"status_code": "", "status": "", "message": ""}

    try:
        body = json.loads(request.body)
        module = body.get('module')
        data = body.get('data')

    except json.JSONDecodeError as e:
        response["status_code"] = 400
        response["status"] = "Bad Request"
        response["message"] = f"Error decoding JSON: {e.msg}"
        return JsonResponse(response)

    try:
        response['status_code'] = 200
        if method == "PUT":
            response['message'] = "Record Saved"
            if module == 'provider':
                name = data.get('name')
                email = data.get('email')
                phone = data.get('phone')
                description = data.get('description')
                country = data.get('country')
                city = data.get('city')
                owner = User.objects.get(pk=data.get('mypk'))
                AppProviders(name=name, email=email, phone=phone, description=description, country=country, city=city,
                             owner=owner).save()

            elif module == 'app_error':
                app = data.get('app')
                title = data.get('title')
                message = data.get('message')

            elif module == 'subscriber':

                name = data.get('name')
                email = data.get('email')
                phone = data.get('phone')
                app_uni = data.get('app_uni')
                app = App.objects.get(uni=app_uni)
                Subscribers.objects.create(
                    name = name,
                    email=email,
                    phone=phone,
                    app=app
                )

                # make sms notification
                sms_message = f"Dear {name}, you have been added on a subscriber list of {app.name}. You will be notified on subsequent updated"
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
                    .footer {{
                      padding: 15px 30px;
                      font-size: 12px;
                      color: #999999;
                      text-align: center;
                      border-top: 1px solid #eeeeee;
                    }}
                    .btn {{
                      display: inline-block;
                      margin-top: 15px;
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
                      <h2>{app.name}</h2>
                    </div>
                    <div class="body">
                      <p>Dear {name},</p>
                      <p>You have been added to the subscriber list of <strong>{app.name}</strong>. You will be notified whenever there are subsequent updates.</p>
                      <a href="#" class="btn">Visit {app.name}</a>
                    </div>
                    <div class="footer">
                      &copy; {app.name}. All rights reserved.
                    </div>
                  </div>
                </body>
                </html>
                """

                Sms.objects.create(
                    api=SmsApi.objects.get(is_default=True),
                    to=phone,
                    message=sms_message
                )

                MailQueues.objects.create(
                    sender=MailSenders.objects.get(is_default=True),
                    recipient=email,
                    subject=f"{app.name} Subscriber List",
                    body=email_template,
                    cc='rootech.inc@proton.me',
                    mail_key=make_md5_hash(email_template)
                )

                response = {"status_code": 200, "message": "Subscriber Saved"}

            else:
                raise Exception("No valid module")

        elif method == 'VIEW':
            if module == 'provider':
                providers = AppProviders.objects.all()
                ps = []
                for provider in providers:
                    ps.append({
                        "name": provider.name,
                        "email": provider.email,
                        "phone": provider.phone,
                        "description": provider.description,
                        "country": provider.country,
                        "city": provider.city,
                        "pk": provider.pk
                    })
                    response['message'] = ps

            elif module == 'subscriber':
                app = App.objects.get(uni=data.get('uni'))
                response['message'] = [sub.obj() for sub in Subscribers.objects.filter(app=app)]

            elif module == 'apps':
                pk = data.get('pk', '*')
                get_by = data.get('get_by','pk')
                if pk == '*':
                    apps = App.objects.all()
                else:
                    if get_by == 'pk':
                        apps = App.objects.filter(pk=pk)
                    else:
                        apps = App.objects.filter(uni=pk)

                apps_list = []
                for app in apps:
                    apps_list.append(app.obj())

                response['message'] = apps_list
                response['status_code'] = 200


            else:
                response['message'] = 'Unknow Module'
                response['status'] = 'error'
                response['status_code'] = 404


    except Exception as e:
        import traceback

        response["status_code"] = 400
        response["status"] = "Error"
        response["message"] = f"{e} {traceback.print_exc(limit=1)} - {traceback.format_exc()}"

    return JsonResponse(response, safe=False)
