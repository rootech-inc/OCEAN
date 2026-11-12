import json

from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.http import JsonResponse
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt

from admin_panel.anton import error_response, success_response, generate_text
from pm.models import Clients, Projects, ProjectTimeline


def _unique_project_url(client_name, title, exclude_pk=None):
    base_slug = slugify(f"{client_name}-{title}") or "project"
    slug = base_slug
    counter = 2
    qs = Projects.objects.all()
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(url=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


@csrf_exempt
def index(request):
    try:
        body = json.loads(request.body)
        method = request.method
        data = body.get('data') or {}
        module = body.get('module')

        if method == 'PUT':
            if module == 'client':
                name = (data.get("name") or "").strip()
                phone = (data.get("phone") or "").strip()
                email = (data.get("email") or "").strip()
                address = (data.get("address") or "").strip()

                if not all([name, phone, email, address]):
                    raise Exception("Name, phone, email, and address are required.")

                client = Clients.objects.create(name=name, phone=phone, email=email, address=address)
                response = success_response(client.obj())

            elif module == 'project':
                p_type = data.get("type")
                client_pk = data.get("client_pk")
                client = Clients.objects.get(pk=client_pk)
                title = (data.get("title") or "").strip()
                description = (data.get("description") or "").strip()
                if not all([p_type, title, description]):
                    raise Exception("Type, title, and description are required.")

                url = _unique_project_url(client.name, title)

                mypk = data.get('mypk')
                created_by = User.objects.get(pk=mypk)

                try:
                    seo_description = generate_text(
                        f"""Generate ONE professional SEO meta description (maximum 160 characters).
                        Return ONLY the description as plain text.
                        No explanations, headings, options, quotation marks, or Markdown.

                        Company: {client.obj()}
                        Project: {title}
                        Description: {description}
                        Target market: Ghana"""
                    )
                except Exception:
                    seo_description = description[:160]

                try:
                    seo_keywords = generate_text(
                        f"""Generate 10-15 relevant SEO keywords for this project.
                        Return ONLY the keywords, separated by commas.
                        No explanations, headings, categories, bullet points, or Markdown.

                        Company: {client.obj()}
                        Project: {title}
                        Description: {description}
                        Target market: Ghana"""
                    )
                except Exception:
                    seo_keywords = f"{client.name}, {title}, {p_type}, Ghana"

                project = Projects.objects.create(
                    client=client,
                    type=p_type,
                    title=title,
                    description=description,
                    seo_description=seo_description,
                    seo_keywords=seo_keywords,
                    url=url,
                    created_by=created_by,
                )

                response = success_response(project.obj())

            elif module == 'update_timeline':
                url = data.get("url")
                project_pk = data.get("project_pk")
                if url:
                    project = Projects.objects.get(url=url)
                elif project_pk:
                    project = Projects.objects.get(pk=project_pk)
                else:
                    raise Exception("Project url or project_pk is required.")

                created_by = User.objects.get(pk=data.get('mypk'))
                title = (data.get("title") or "").strip()
                description = (data.get("description") or "").strip()
                p_date = data.get("date")

                if not all([title, description, p_date]):
                    raise Exception("Title, description, and date are required.")

                timeline = ProjectTimeline.objects.create(
                    project=project,
                    title=title,
                    description=description,
                    created_by=created_by,
                    date=p_date,
                )

                response = success_response({
                    'timeline': timeline.obj(),
                    'project': project.obj(),
                })

            else:
                raise Exception('Module Not Supported')

        elif method == 'VIEW':
            if module == 'client':
                pk = data.get("pk", '*')
                result = Clients.objects.get(pk=pk).obj() if pk != '*' else [
                    cl.obj() for cl in Clients.objects.all().order_by('-date_created')
                ]
                response = success_response(result)

            elif module == 'project':
                url = data.get("url", '*')
                pk = data.get("pk")
                if pk:
                    result = Projects.objects.get(pk=pk).obj()
                elif url == '*':
                    qs = Projects.objects.select_related('client', 'created_by').all().order_by('-created_at')
                    if data.get('client_pk'):
                        qs = qs.filter(client_id=data.get('client_pk'))
                    if data.get('type'):
                        qs = qs.filter(type=data.get('type'))
                    if data.get('status') == 'open':
                        qs = qs.filter(is_open=True, is_closed=False)
                    elif data.get('status') == 'closed':
                        qs = qs.filter(is_closed=True)
                    result = [pj.obj() for pj in qs]
                else:
                    result = Projects.objects.get(url=url).obj()

                response = success_response(result)

            elif module == 'update_timeline':
                pk = data.get("pk")
                url = data.get("url")
                if pk:
                    result = ProjectTimeline.objects.get(pk=pk).obj()
                elif url:
                    project = Projects.objects.get(url=url)
                    result = [
                        tl.obj() for tl in ProjectTimeline.objects.filter(project=project).order_by('-date', '-created_at')
                    ]
                else:
                    result = [tl.obj() for tl in ProjectTimeline.objects.all().order_by('-date', '-created_at')]
                response = success_response(result)

            else:
                raise Exception('Module Not Supported')

        elif method == 'PATCH':
            if module == 'client':
                pk = data.get("pk")
                client = Clients.objects.get(pk=pk)
                if "name" in data and data.get("name") is not None:
                    client.name = data.get("name").strip()
                if "email" in data and data.get("email") is not None:
                    client.email = data.get("email").strip()
                if "phone" in data and data.get("phone") is not None:
                    client.phone = data.get("phone").strip()
                if "address" in data and data.get("address") is not None:
                    client.address = data.get("address").strip()
                client.save()
                response = success_response(client.obj())

            elif module == 'project':
                pk = data.get("pk")
                url = data.get("url")
                if pk:
                    project = Projects.objects.get(pk=pk)
                elif url:
                    project = Projects.objects.get(url=url)
                else:
                    raise Exception("Project pk or url is required.")

                if data.get("client_pk"):
                    project.client = Clients.objects.get(pk=data.get("client_pk"))
                if data.get("type"):
                    project.type = data.get("type")
                if "title" in data and data.get("title") is not None:
                    project.title = data.get("title").strip()
                if "description" in data and data.get("description") is not None:
                    project.description = data.get("description").strip()
                if "seo_description" in data and data.get("seo_description") is not None:
                    project.seo_description = data.get("seo_description").strip()
                if "seo_keywords" in data and data.get("seo_keywords") is not None:
                    project.seo_keywords = data.get("seo_keywords").strip()
                if "is_open" in data and data.get("is_open") is not None:
                    project.is_open = bool(data.get("is_open"))
                if "is_closed" in data and data.get("is_closed") is not None:
                    project.is_closed = bool(data.get("is_closed"))

                project.save()
                response = success_response(project.obj())

            elif module == 'update_timeline':
                pk = data.get("pk")
                timeline = ProjectTimeline.objects.get(pk=pk)
                if "title" in data and data.get("title") is not None:
                    timeline.title = data.get("title").strip()
                if "description" in data and data.get("description") is not None:
                    timeline.description = data.get("description").strip()
                if "date" in data and data.get("date") is not None:
                    timeline.date = data.get("date")
                timeline.save()
                response = success_response({
                    'timeline': timeline.obj(),
                    'project': timeline.project.obj(),
                })

            else:
                raise Exception('Module Not Supported')

        elif method == 'DELETE':
            if module == 'client':
                pk = data.get("pk")
                client = Clients.objects.get(pk=pk)
                try:
                    client.delete()
                except ProtectedError:
                    raise Exception("Cannot delete this client because it has associated projects.")
                response = success_response("Client deleted successfully")

            elif module == 'project':
                pk = data.get("pk")
                url = data.get("url")
                if pk:
                    project = Projects.objects.get(pk=pk)
                elif url:
                    project = Projects.objects.get(url=url)
                else:
                    raise Exception("Project pk or url is required.")

                try:
                    project.delete()
                except ProtectedError:
                    raise Exception("Cannot delete this project because it has timeline updates. Delete the timeline updates first.")
                response = success_response("Project deleted successfully")

            elif module == 'update_timeline':
                pk = data.get("pk")
                timeline = ProjectTimeline.objects.get(pk=pk)
                project = timeline.project
                timeline.delete()
                response = success_response(project.obj())

            else:
                raise Exception('Module Not Supported')

        else:
            response = error_response("Invalid method")
    except Exception as ex:
        response = error_response(str(ex))

    return JsonResponse(response, safe=False)
