import random

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.sites import requests
from django.core.mail import send_mail
from django.db import models
from django.utils.text import slugify

import blog.urls
from django.contrib.messages.storage import session
from django.http import HttpResponseRedirect
from django.shortcuts import render, HttpResponse, redirect
from blog.forms import *
from blog.anton import *
from blog.models import *
from community.models import *
from django.views.decorators.csrf import csrf_exempt
from admin_panel.anton import make_thumbnail

# general values
search_form = SearchForm()
all_meta = article_meta.objects.all()


def resolve_blog_meta(title, content, custom_uni=None, custom_intro=None, custom_meta=None, tags=None, current_pk=None):
    """
    Resolves blog URL (uni), SEO description (intro), and keywords (meta).
    If custom values are provided by the user, cleans and validates them.
    If not provided, uses current auto-generation mechanisms with fallback.
    Guarantees unique uni across articles.
    """
    # 1. Resolve uni (URL slug)
    cleaned_uni = (custom_uni or "").strip().lower()
    if cleaned_uni:
        base_slug = slugify(cleaned_uni)
        if not base_slug:
            base_slug = slugify(title.strip()) or "article"
    else:
        # Current mechanism: tags + title
        tag_str = (tags or "").strip()
        base_str = f"{tag_str} {title}".strip() if tag_str else title.strip()
        base_slug = slugify(base_str) or "article"

    base_slug = base_slug[:180]
    slug = base_slug
    counter = 2
    qs = articles.objects.all()
    if current_pk:
        qs = qs.exclude(pk=current_pk)
    while qs.filter(uni=slug).exists():
        slug = f"{base_slug[:175]}-{counter}"
        counter += 1

    # 2. Resolve intro (SEO description)
    cleaned_intro = (custom_intro or "").strip()
    plain_content = remove_tags(content).strip() if content else ""
    if cleaned_intro:
        intro = cleaned_intro[:500]
    else:
        # Current mechanism: Anton AI generate_text, fallback to first 160 chars of plain text
        try:
            from admin_panel.anton import generate_text
            summary_prompt = f"Summarize this blog post in one concise sentence (maximum 160 characters). Return ONLY plain text:\n\nTitle: {title}\nContent: {plain_content[:600]}"
            generated = generate_text(summary_prompt)
            if generated and generated.strip():
                intro = generated.strip().replace('"', '').replace("'", "")[:250]
            else:
                intro = plain_content[:160].strip() or title
        except Exception:
            intro = plain_content[:160].strip() or title

    # 3. Resolve meta (Keywords)
    cleaned_meta = (custom_meta or "").strip()
    if cleaned_meta:
        meta = cleaned_meta[:200]
    else:
        # Current mechanism: tags or title
        tag_str = (tags or "").strip()
        meta = tag_str[:200] if tag_str else f"{title}, ocean, guide"[:200]

    return slug, intro, meta


# Create your views here.
@login_required()
def index(request):
    all_articles = articles.objects.all().select_related('author').order_by('-id')

    q = request.GET.get('q', '').strip()
    tag_filter = request.GET.get('tag', '').strip()

    if q:
        all_articles = all_articles.filter(
            models.Q(title__icontains=q) |
            models.Q(intro__icontains=q) |
            models.Q(tag__icontains=q) |
            models.Q(meta__icontains=q)
        )
    if tag_filter:
        all_articles = all_articles.filter(tag__iexact=tag_filter)

    all_tags = articles.objects.exclude(tag='').values_list('tag', flat=True).distinct()[:12]

    context = {
        'nav': True,
        'page_title': 'Ocean Blog & Guides',
        'articles': all_articles,
        'tags': all_tags,
        'current_tag': tag_filter,
        'search_query': q,
        'total_count': all_articles.count(),
    }
    return render(request, 'blog/index.html', context)


@login_required()
def article(request, title):
    if articles.objects.filter(uni=title).exists():
        this_article = articles.objects.get(uni=title)
    elif articles.objects.filter(title=title).exists():
        this_article = articles.objects.filter(title=title).first()
    else:
        return redirect('blog-home')

    user_id = request.user.id if request.user.is_authenticated else 0

    if ArticleView.objects.filter(article=this_article.uni, user=user_id).count() < 1:
        ArticleView(article=this_article.uni, user=user_id).save()

    view_count = ArticleView.objects.filter(article=this_article.uni).count()
    related_articles = articles.objects.filter(tag=this_article.tag).exclude(pk=this_article.pk)[:3]
    if not related_articles.exists():
        related_articles = articles.objects.exclude(pk=this_article.pk).order_by('-id')[:3]

    context = {
        'page_title': f'{this_article.title} | Ocean Blog',
        'page': {
            'description': this_article.intro,
            'keywords': this_article.meta,
        },
        'article': this_article,
        'view_count': view_count,
        'related_articles': related_articles,
        'nav': True,
    }
    return render(request, 'blog/article.html', context)


def search(request):
    if request.method == 'POST':

        s_form = SearchForm(request.POST)
        if s_form.is_valid():
            query = s_form.cleaned_data['query']
            return redirect('search-result', query)
            # return HttpResponse("<h1>"+str(query)+"</h1>")
        else:
            return HttpResponse("<h1>Form Not Valid..</h1>")

    else:
        return HttpResponse("<h1>Method is not posting..</h1>")
    # return render(request, 'blog/search-result.html')


def search_result(request, query):
    # get user keywords
    if 'login' not in request.session:
        logedin = False
        username = False
        meta_kword = False
        query_res = articles.objects.filter(meta='public')
        # return redirect('blog-home')
    else:
        logedin = request.session['login']
        username = request.session['user']

        user_details = userAccounts.objects.get(username=username)
        meta_kword = user_details.meta_words
        if meta_kword == '*':
            query_res = articles.objects.filter(intro__regex=query)
        else:
            query_res = articles.objects.filter(meta__contains=meta_kword, intro__regex=query)

    res_count = query_res.count()

    context = {
        'page_title': ' Ocean | Found | ' + str(query[0:20]),
        'result': query_res, 'result_count': res_count, 'query_str': query,
        'login': {
            'status': logedin, 'myname': username, 'mymeta': meta_kword
        }
    }
    return render(request, 'blog/search-result.html', context=context)

@login_required()
def new_article(request):
    meta_data = tags.objects.all().order_by('tag_dec')
    existing_tags = list(articles.objects.exclude(tag='').values_list('tag', flat=True).distinct()[:15])
    context = {
        'page_title': 'New Article',
        'meta_dat': meta_data,
        'existing_tags': existing_tags,
        'scope_choices': articles.scope_type,
        'nav': True
    }
    return render(request, 'blog/new-article.html', context=context)

@login_required()
def save_article(request):
    if request.method == 'POST':
        page_title = (request.POST.get('page_title') or '').strip()
        article_desc_raw_htm = (request.POST.get('article_desc') or '').strip()
        custom_uni = (request.POST.get('custom_uni') or request.POST.get('uni') or '').strip()
        tags_val = (request.POST.get('tags') or request.POST.get('tag') or '').strip()
        custom_intro = (request.POST.get('intro') or '').strip()
        custom_meta = (request.POST.get('meta') or '').strip()
        scope = request.POST.get('scope', 'public')

        if not page_title:
            return HttpResponse('Article title is required.', status=400)

        slug, intro, meta = resolve_blog_meta(
            title=page_title,
            content=article_desc_raw_htm,
            custom_uni=custom_uni,
            custom_intro=custom_intro,
            custom_meta=custom_meta,
            tags=tags_val,
        )

        author = request.user if request.user.is_authenticated else None

        article_save = articles(
            uni=slug,
            title=page_title,
            article=article_desc_raw_htm,
            intro=intro,
            tag=tags_val or 'General',
            meta=meta,
            scope=scope,
            author=author,
        )

        if 'post_img' in request.FILES:
            post_img = request.FILES['post_img']
            article_save.image = post_img
            article_save.thumbnail = make_thumbnail(post_img)

        article_save.save()
        return redirect('article', slug)

    return HttpResponse("Not Posted Form", status=405)

@login_required()
def load_meta(request, meta):
    all_articles = articles.objects.filter(meta=meta)
    cats = tags.objects.all()
    context = {
        'page_title': 'Articles',
        'articles': all_articles,
        'tags': cats
    }
    return render(request, 'blog/meta-load.html', context=context)

@login_required()
def login(request):
    if request.user.is_authenticated:
        return redirect('blog-home')

    if request.method == 'GET' and 'next' in request.GET:
        next_page = request.GET['next']
    else:
        next_page = 'blog-home'
    context = {
        'page_title': 'Ocean | Login',
        'form': LogIn(),
        'next': next_page
    }
    return render(request, 'blog/login.html', context=context)

@login_required()
def login_process(request):
    if request.method == 'POST':
        form = LogIn(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            next = form.cleaned_data['next']

            # check if user exist
            user = authenticate(request, username=username, password=password)

            try:
                # check if user is valid
                if hasattr(user, 'is_active'):
                    auth_login(request, user)
                    # Redirect to a success page.
                    return redirect(next)
                else:
                    messages.error(request,
                                   f"There is an error logging in, please check your credentials again or contact Administrator")
                    return redirect('login')

            except Exception as e:
                messages.error(request, f"There was an error {e}")
                return redirect('login')

        else:
            return HttpResponse("Invalid Form")
    else:
        pass

@login_required()
def logout_view(request):
    logout(request)
    return redirect('blog-home')

@login_required()
def edit_article(request, uni):
    try:
        this_article = articles.objects.get(uni=uni)
    except articles.DoesNotExist:
        if articles.objects.filter(title=uni).exists():
            this_article = articles.objects.filter(title=uni).first()
        else:
            return redirect('blog-home')

    existing_tags = list(articles.objects.exclude(tag='').values_list('tag', flat=True).distinct()[:15])
    meta_data = tags.objects.all()
    context = {
        'page_title': f'Edit Article | {this_article.title}',
        'article': this_article,
        'existing_tags': existing_tags,
        'scope_choices': articles.scope_type,
        'meta_dat': meta_data,
        'nav': True,
    }
    return render(request, 'blog/edit_article.html', context)


@login_required()
def edit_save(request):
    if request.method == 'POST':
        original_uni = request.POST.get('original_uni') or request.POST.get('uni')
        try:
            target_article = articles.objects.get(uni=original_uni)
        except articles.DoesNotExist:
            if articles.objects.filter(title=original_uni).exists():
                target_article = articles.objects.filter(title=original_uni).first()
            else:
                return HttpResponse('Article not found', status=404)

        page_title = (request.POST.get('page_title') or '').strip()
        article_desc_raw_htm = (request.POST.get('article_desc') or '').strip()
        custom_uni = (request.POST.get('custom_uni') or request.POST.get('uni') or '').strip()
        tags_val = (request.POST.get('tags') or request.POST.get('tag') or '').strip()
        custom_intro = (request.POST.get('intro') or '').strip()
        custom_meta = (request.POST.get('meta') or '').strip()
        scope = request.POST.get('scope', target_article.scope)

        if not page_title:
            return HttpResponse('Article title is required.', status=400)

        slug, intro, meta = resolve_blog_meta(
            title=page_title,
            content=article_desc_raw_htm,
            custom_uni=custom_uni if custom_uni != original_uni else original_uni,
            custom_intro=custom_intro,
            custom_meta=custom_meta,
            tags=tags_val or target_article.tag,
            current_pk=target_article.pk,
        )

        target_article.title = page_title
        target_article.article = article_desc_raw_htm
        target_article.uni = slug
        target_article.intro = intro
        target_article.meta = meta
        target_article.tag = tags_val or target_article.tag
        target_article.scope = scope

        if 'post_img' in request.FILES:
            new_img = request.FILES['post_img']
            target_article.image = new_img
            target_article.thumbnail = make_thumbnail(new_img)

        target_article.save()
        return redirect('article', slug)

    return HttpResponse("Not Posted Form", status=405)


def finder(request):
    all_articles = articles.objects.all()[:50]
    cats = tags.objects.all()
    context = {
        'page_title': 'Articles',
        'articles': all_articles,
        'tags': cats,
        'nav':True
    }
    return render(request, 'blog/finder.html', context=context)


def new_user(request):
    context = {
        'page_title': 'Ocean | Register',
        'form': LogIn()
    }
    return render(request, 'blog/register.html', context=context)


def sign_up(request):
    if request.method == 'POST':
        form = SignUp(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            # generate username
            number = '{:03d}'.format(random.randrange(1, 9999))
            username = '{}{}'.format(last_name, number)

            # save username
            new_user_instance = User.objects.create_user(username=username, password=password, email=email,
                                                         first_name=first_name, last_name=last_name)

            try:
                new_user_instance.save()
                new_user_instance.is_active = False
                subject = 'welcome to OCEAN'
                message = f'Hi {first_name} {last_name}, thank you for registering in ocean. your username is {username} and password is {password} logn at ocean t explore the power in collaboration '
                email_from = settings.EMAIL_HOST_USER
                recipient_list = [email]
                send_mail(subject, message, email_from, recipient_list)
                messages.error(request, "Please check your email to activate your account")
                return redirect('new-user')
            except:
                messages.error(request, "Error Saving User")
                return redirect('new-user')

        else:
            return HttpResponse("Invalid Form")
    else:
        return HttpResponse("Unaccepted Form Method")


def article_convo(request):
    if request.method == 'POST':
        form = request.POST
        convo_message = form['convo_message']
        post = form['article']
        current_user = request.user
        try:
            ArticleChat(sent_from=current_user.pk, message=convo_message, article=post).save()
            return HttpResponse('done%%msg_sent')
        except Exception as e:
            return HttpResponse(f'error%%{e}')


def load_convo(request):
    if request.method == 'GET':
        form = request.GET
        article_pk = form['article_pk']
        msgs = ArticleChat.objects.filter(article=article_pk)
        current_user = request.user
        row = ''
        if ArticleChat.objects.filter(article=article_pk).count() > 0:
            # loop through
            for msg in msgs:
                user = User.objects.get(pk=msg.sent_from)
                float_class = ''
                text = ''
                header = f'<span class="badge badge-info {float_class}">@{user.username}</span><br>'
                if current_user.pk == msg.sent_from:
                    float_class = 'float-right'
                    text = 'text-right'
                    header = f''
                else:
                    header = f'<span class="badge badge-info {float_class}">@{user.username}</span><br>'

                row += f'<div class="w-100 message-box">\
                            <div class="w-100 p-2 rounded">\
                                {header}\
                                <div class="bg-animate {text}"><small>{msg.message} </small></div>\
                            </div>\
                        </div>'


        else:
            row += "<div class='w-100 h-100 d-flex flex-wrap align-content-center justify-content-center'>NO " \
                   "MESSAGE</div> "
            # no article
        return HttpResponse(row)
    else:
        return HttpResponse('error%%Unknown Method')


from django.template import RequestContext


def handler404(request, *args, **argv):
    response = render(request, '404.html', {})
    response.status_code = 404
    return response


def print_article(request,uni):
    art = articles.objects.get(uni=uni)
    return render(request,'blog/print-page.html',context={'article':art})


@csrf_exempt
def upload_image(request):
    if request.method == 'POST':
        form = request.POST
        image = request.FILES['post_img']
        uni = form['uni']
        try:
            # save image
            article = articles.objects.get(uni=uni)

            # make thumbnail



            article.image = image
            article.thumbnail = make_thumbnail(image)
            article.save()
            return redirect('article',uni)
        except Exception as e:
            return HttpResponse(f'error%%{e}')