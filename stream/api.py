import json
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from stream.models import Videos, Comments, Views
from admin_panel.anton import get_client_ip

@csrf_exempt
def stream_api(request):
    response = {
        'status_code': 0,
        'message': ""
    }

    success_response = {
        'status_code': 200,
        'message': "Procedure Completed Successfully"
    }

    method = request.method

    try:
        body = json.loads(request.body)
        module = body.get('module')
        data = body.get('data')

        if method == 'PUT':
            if module == 'comment':
                video_key = data.get('video_key')
                text = data.get('text')
                user_pk = data.get('user_pk')

                if not text:
                    raise Exception("Comment text is required")

                video = Videos.objects.get(key=video_key)
                user = User.objects.get(pk=user_pk)

                Comments.objects.create(user=user, video=video, text=text)

                success_response['message'] = "Comment Added"
                response = success_response

            elif module == 'view':
                video_key = data.get('video_key')
                ip = get_client_ip(request)
                
                # Optional: Check if user is logged in
                user = request.user if request.user.is_authenticated else None

                video = Videos.objects.get(key=video_key)
                
                # Basic logic to prevent duplicate view counting from same IP within short time could go here
                # For now, just log it.
                Views.objects.create(video=video, ip=ip, user=user)
                
                # Update total count
                video.views_count += 1
                video.save()

                success_response['message'] = "View Counted"
                response = success_response
            
            else:
                raise Exception("Invalid module for PUT")

        elif method == 'VIEW':
            if module == 'comment':
                video_key = data.get('video_key')
                video = Videos.objects.get(key=video_key)
                comments = Comments.objects.filter(video=video).order_by('-created_at')

                arr = []
                for c in comments:
                    arr.append({
                        'id': c.id,
                        'user': c.user.username,
                        'avatar': c.user.username[:1].upper(), # Simple avatar fallback
                        'text': c.text,
                        'created_at': c.created_at.strftime("%b %d, %Y, %I:%M %p"), # Format date
                        'is_owner': request.user == c.user
                    })

                success_response['message'] = arr
                response = success_response
            else:
                 raise Exception("Invalid module for VIEW")

        elif method == 'DELETE':
             if module == 'comment':
                comment_id = data.get('comment_id')
                # Security check: ensure user owns comment or is superuser
                # This part relies on the session user, but the API might be called from JS where request.user is available via session auth
                
                try:
                    comment = Comments.objects.get(id=comment_id)
                    if request.user == comment.user or request.user.is_superuser:
                        comment.delete()
                        success_response['message'] = "Comment Deleted"
                    else:
                        raise Exception("Unauthorized")
                except Comments.DoesNotExist:
                     raise Exception("Comment not found")
                
                response = success_response
             else:
                 raise Exception("Invalid module for DELETE")

    except Exception as e:
        response['status_code'] = 500
        response['message'] = str(e)

    from django.http import JsonResponse
    return JsonResponse(response)
