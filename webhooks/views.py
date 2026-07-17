# views.py
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

VERIFY_TOKEN = "Szczesny@411"

@csrf_exempt
def whatsapp_webhook(request):
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse("Verification failed", status=403)

    elif request.method == "POST":
        data = json.loads(request.body)
        # TODO: process incoming messages / status updates
        print(data)  # inspect structure while testing
        return JsonResponse({"status": "ok"}, status=200)


def index(request):
    return None