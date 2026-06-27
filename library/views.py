from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .forms import MemeCreateForm, MemeUpdateForm
from .models import Meme, Tag
from .services import (
    ImageImportError,
    extension_for_format,
    fetch_remote_image,
    inspect_image,
    make_thumbnail,
    read_limited_upload,
    strip_image_metadata,
)

MEME_PAGE_SIZE = 36


def normalize_tags(raw_tags):
    names = []
    seen = set()
    for raw in (raw_tags or '').split(','):
        name = ' '.join(raw.strip().lower().split())
        if not name or name in seen:
            continue
        if len(name) > 64:
            raise ValueError('Tags must be 64 characters or fewer.')
        seen.add(name)
        names.append(name)
    if len(names) > 24:
        raise ValueError('Use 24 tags or fewer per meme.')
    return names


def set_tags(meme, raw_tags):
    tag_names = normalize_tags(raw_tags)
    tags = []
    for name in tag_names:
        tag, _ = Tag.objects.get_or_create(name=name)
        tags.append(tag)
    meme.tags.set(tags)


@login_required
def index(request):
    query = request.GET.get('q', '').strip()
    paginator, page = paginate_memes(search_memes(query), 1)
    popular_tags = Tag.objects.annotate(meme_count=Count('memes')).filter(meme_count__gt=0)[:30]
    return render(
        request,
        'library/index.html',
        {
            'form': MemeCreateForm(),
            'memes': page.object_list,
            'has_next_page': page.has_next(),
            'next_page': page.next_page_number() if page.has_next() else '',
            'total_count': paginator.count,
            'page_size': MEME_PAGE_SIZE,
            'query': query,
            'popular_tags': popular_tags,
        },
    )


@login_required
@require_POST
def create_meme(request):
    form = MemeCreateForm(request.POST, request.FILES)
    if not form.is_valid():
        for error in form.non_field_errors():
            messages.error(request, error)
        return redirect('library:index')

    try:
        with transaction.atomic():
            meme = build_meme_from_form(form, request.user)
            set_tags(meme, form.cleaned_data.get('tags', ''))
        messages.success(request, 'Meme added.')
    except (ImageImportError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect('library:index')


def build_meme_from_form(form, user):
    upload = form.cleaned_data.get('image')
    image_url = form.cleaned_data.get('image_url')

    if upload:
        data = read_limited_upload(upload)
    else:
        data = fetch_remote_image(image_url)

    source_info = inspect_image(data)
    sanitized_data, info = strip_image_metadata(data, source_info['format'])
    suffix = extension_for_format(info['format'])
    title = form.cleaned_data.get('title', '').strip()
    meme = Meme(
        title=title,
        content_type=info['content_type'],
        width=info['width'],
        height=info['height'],
        size=len(sanitized_data),
        created_by=user,
    )
    meme.original.save(f'original{suffix}', ContentFile(sanitized_data), save=False)
    meme.thumbnail.save('thumbnail.jpg', make_thumbnail(sanitized_data), save=False)
    meme.save()
    return meme


@login_required
@require_http_methods(['GET', 'POST'])
def edit_meme(request, pk):
    meme = get_object_or_404(Meme.objects.prefetch_related('tags'), pk=pk)
    if request.method == 'POST':
        form = MemeUpdateForm(request.POST)
        if form.is_valid():
            try:
                title = form.cleaned_data.get('title', '').strip()
                if title != meme.title:
                    meme.title = title
                    meme.public_slug = Meme.make_unique_public_slug(title, instance_pk=meme.pk)
                    meme.save(update_fields=['title', 'public_slug', 'updated_at'])
                else:
                    meme.save(update_fields=['updated_at'])
                set_tags(meme, form.cleaned_data.get('tags', ''))
                messages.success(request, 'Meme updated.')
                return redirect('library:index')
            except ValueError as exc:
                messages.error(request, str(exc))
    else:
        form = MemeUpdateForm(
            initial={
                'title': meme.title,
                'tags': ','.join(meme.tags.values_list('name', flat=True)),
            }
        )
    return render(request, 'library/edit.html', {'form': form, 'meme': meme})


@login_required
@require_POST
def delete_meme(request, pk):
    meme = get_object_or_404(Meme, pk=pk)
    original = meme.original
    thumbnail_file = meme.thumbnail
    meme.delete()
    if original:
        original.delete(save=False)
    if thumbnail_file:
        thumbnail_file.delete(save=False)
    messages.success(request, 'Meme deleted.')
    return redirect('library:index')


@login_required
def thumbnail(request, pk):
    meme = get_object_or_404(Meme, pk=pk)
    if not meme.thumbnail:
        raise Http404
    return FileResponse(meme.thumbnail.open('rb'), content_type='image/jpeg')


def public_image(request, token, filename):
    public_slug = filename.rsplit('.', 1)[0]
    meme = get_object_or_404(Meme, public_token=token, public_slug=public_slug)
    response = FileResponse(meme.original.open('rb'), content_type=meme.content_type or 'application/octet-stream')
    response['Content-Disposition'] = f'inline; filename="{meme.download_filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def download_meme(request, pk):
    meme = get_object_or_404(Meme, pk=pk)
    response = FileResponse(meme.original.open('rb'), content_type=meme.content_type or 'application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{meme.download_filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def tag_search_api(request):
    query = request.GET.get('q', '').strip().lower()
    tags = Tag.objects.all()
    if query:
        tags = tags.filter(name__icontains=query)
    return JsonResponse({'tags': [{'id': tag.id, 'name': tag.name} for tag in tags[:20]]})


@login_required
def meme_search_api(request):
    query = request.GET.get('q', '').strip()
    page_number = request.GET.get('page', 1)
    paginator, page = paginate_memes(search_memes(query), page_number)
    return JsonResponse(
        {
            'memes': [serialize_meme(request, meme) for meme in page.object_list],
            'page': page.number,
            'pageSize': MEME_PAGE_SIZE,
            'total': paginator.count,
            'hasNext': page.has_next(),
            'nextPage': page.next_page_number() if page.has_next() else None,
        }
    )


def search_memes(query):
    memes = Meme.objects.prefetch_related('tags')
    if query:
        terms = [term for term in query.split() if term]
        for term in terms:
            memes = memes.filter(
                Q(title__icontains=term)
                | Q(tags__name__icontains=term)
            )
    return memes.distinct()


def paginate_memes(memes, page_number):
    paginator = Paginator(memes, MEME_PAGE_SIZE)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    return paginator, page


def serialize_meme(request, meme):
    return {
        'id': meme.id,
        'title': meme.display_title,
        'tags': list(meme.tags.values_list('name', flat=True)),
        'thumbnailUrl': reverse('library:thumbnail', kwargs={'pk': meme.pk}),
        'publicUrl': request.build_absolute_uri(meme.public_url()),
        'downloadUrl': reverse('library:download', kwargs={'pk': meme.pk}),
        'editUrl': reverse('library:edit', kwargs={'pk': meme.pk}),
        'deleteUrl': reverse('library:delete', kwargs={'pk': meme.pk}),
        'width': meme.width,
        'height': meme.height,
        'size': meme.size,
    }
