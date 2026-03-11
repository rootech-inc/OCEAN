from django.shortcuts import render

# Create your views here.
def index(request):
    context = {
        'page': {
            'title': 'Anton AI'
        }
    }
    return render(request, 'anton/index.html', context)
