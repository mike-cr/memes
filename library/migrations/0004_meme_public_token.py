import uuid

from django.db import migrations, models


def populate_public_tokens(apps, schema_editor):
    Meme = apps.get_model('library', 'Meme')
    used = set()

    for meme in Meme.objects.order_by('id'):
        while True:
            token = uuid.uuid4().hex[:8]
            if token not in used and not Meme.objects.filter(public_token=token).exclude(pk=meme.pk).exists():
                break
        meme.public_token = token
        meme.save(update_fields=['public_token'])
        used.add(token)


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0003_meme_public_slug_meme_library_mem_public__983f97_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='meme',
            name='public_token',
            field=models.CharField(blank=True, max_length=12, null=True),
        ),
        migrations.RunPython(populate_public_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='meme',
            name='public_token',
            field=models.CharField(blank=True, max_length=12, unique=True),
        ),
    ]
