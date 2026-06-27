from django.conf import settings
from django.db import migrations, models
from django.utils.text import slugify


def populate_public_slugs(apps, schema_editor):
    Meme = apps.get_model('library', 'Meme')
    used = set()

    for meme in Meme.objects.order_by('id'):
        base_slug = slugify(meme.title)[:170] or 'meme'
        slug = base_slug
        counter = 2
        while slug in used or Meme.objects.filter(public_slug=slug).exclude(pk=meme.pk).exists():
            slug = f'{base_slug}-{counter}'[:190]
            counter += 1
        meme.public_slug = slug
        meme.save(update_fields=['public_slug'])
        used.add(slug)


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0002_remove_meme_original_filename_remove_meme_source_url'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='meme',
            name='public_slug',
            field=models.SlugField(blank=True, max_length=190, null=True),
        ),
        migrations.RunPython(populate_public_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='meme',
            name='public_slug',
            field=models.SlugField(blank=True, max_length=190, unique=True),
        ),
    ]
