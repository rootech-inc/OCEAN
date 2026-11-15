import json
import sys

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from admin_panel.anton import make_md5_hash, generate_text
from blog.models import articles


@csrf_exempt
def interface(request):
    response = {
        'status_code': 0,
        'message': ""
    }

    success_response = {
        'status_code': 200,
        'message': "Procedure Completed Successfully"
    }

    # get method
    method = request.method

    try:

        body = json.loads(request.body)
        module = body.get('module')
        data = body.get('data')

        if method == 'PUT':
            success_response['message'] = "Data Added"
            if module == 'new_article':
                from blog.views import resolve_blog_meta
                owner = data.get('mypk') or data.get('owner')
                title = (data.get('title') or '').strip()
                content = (data.get('content') or '').strip()
                author = User.objects.get(pk=owner) if owner else None
                tags = (data.get('tags') or '').strip()
                custom_uni = data.get('uni')
                custom_intro = data.get('intro')
                custom_meta = data.get('meta')
                scope = data.get('scope', 'public')

                slug, intro, meta = resolve_blog_meta(
                    title=title,
                    content=content,
                    custom_uni=custom_uni,
                    custom_intro=custom_intro,
                    custom_meta=custom_meta,
                    tags=tags,
                )

                new_article = articles(
                    uni=slug,
                    article=content,
                    author=author,
                    tag=tags or 'General',
                    title=title,
                    intro=intro,
                    meta=meta,
                    scope=scope,
                )
                new_article.save()
                success_response['message'] = slug
        elif method == 'VIEW':
            if module == 'article':
                uni = data.get('uni','*')
                scope = data.get('scope','*')

                if uni == '*':
                    if scope == '*':
                        success_response['message'] = [bg.obj() for bg in articles.objects.all()]
                    else:
                        success_response['message'] = [bg.obj() for bg in articles.objects.filter(scope=scope)]
                else:
                    success_response['message'] = [articles.objects.get(uni=uni).obj()]


        else:
            success_response['status_code'] = 404
            success_response['message'] = "Unknown Method"
        response = success_response

    except Exception as e:
        error_type, error_instance, traceback = sys.exc_info()
        tb_path = traceback.tb_frame.f_code.co_filename
        line_number = traceback.tb_lineno
        response["status_code"] = 500
        response[
            "message"] = f"An error of type {error_type} occurred on line {line_number} in file {tb_path}. Details: {e}"

    return JsonResponse(response)
