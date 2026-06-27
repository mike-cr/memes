import uuid

from django.db import migrations
from django.utils.text import slugify


def unique_slug(Meme, title, pk):
    base_slug = slugify(title)[:170] or 'meme'
    slug = base_slug
    counter = 2
    while Meme.objects.filter(public_slug=slug).exclude(pk=pk).exists():
        slug = f'{base_slug}-{counter}'[:190]
        counter += 1
    return slug


def unique_token(Meme, pk):
    while True:
        token = uuid.uuid4().hex[:8]
        if not Meme.objects.filter(public_token=token).exclude(pk=pk).exists():
            return token


def backfill_public_links(apps, schema_editor):
    Meme = apps.get_model('library', 'Meme')
    for meme in Meme.objects.filter(public_slug=''):
        meme.public_slug = unique_slug(Meme, meme.title, meme.pk)
        meme.save(update_fields=['public_slug'])
    for meme in Meme.objects.filter(public_token=''):
        meme.public_token = unique_token(Meme, meme.pk)
        meme.save(update_fields=['public_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0004_meme_public_token'),
    ]

    operations = [
        migrations.RunPython(backfill_public_links, migrations.RunPython.noop),
    ]
