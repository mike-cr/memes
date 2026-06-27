from pathlib import Path
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def original_upload_path(instance, filename):
    suffix = Path(filename).suffix.lower()[:12] or '.img'
    return f'memes/originals/{instance.public_id}{suffix}'


def thumbnail_upload_path(instance, filename):
    return f'memes/thumbnails/{instance.public_id}.jpg'


class Tag(models.Model):
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.strip().split())
        if not self.slug:
            base_slug = slugify(self.name)[:70] or 'tag'
            slug = base_slug
            counter = 2
            while Tag.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'[:80]
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Meme(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    public_slug = models.SlugField(max_length=190, unique=True, blank=True)
    public_token = models.CharField(max_length=12, unique=True, blank=True)
    title = models.CharField(max_length=160, blank=True)
    original = models.ImageField(upload_to=original_upload_path)
    thumbnail = models.ImageField(upload_to=thumbnail_upload_path, blank=True)
    content_type = models.CharField(max_length=64, blank=True)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    size = models.PositiveBigIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    tags = models.ManyToManyField(Tag, related_name='memes', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['public_id']),
        ]

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        return self.title or f'meme-{self.public_id.hex[:8]}'

    def public_url(self):
        return reverse(
            'library:public_image',
            kwargs={'token': self.public_token, 'filename': self.download_filename},
        )

    @property
    def download_filename(self):
        suffix = Path(self.original.name).suffix.lower() or '.img'
        return f'{self.public_slug or "meme"}{suffix}'

    def save(self, *args, **kwargs):
        generated_fields = set()
        if not self.public_slug:
            self.public_slug = self.make_unique_public_slug(self.title)
            generated_fields.add('public_slug')
        if not self.public_token:
            self.public_token = self.make_unique_public_token()
            generated_fields.add('public_token')
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and generated_fields:
            kwargs['update_fields'] = set(update_fields) | generated_fields
        super().save(*args, **kwargs)

    @classmethod
    def make_unique_public_slug(cls, title, instance_pk=None):
        base_slug = slugify(title)[:170] or 'meme'
        slug = base_slug
        counter = 2
        while cls.objects.filter(public_slug=slug).exclude(pk=instance_pk).exists():
            slug = f'{base_slug}-{counter}'[:190]
            counter += 1
        return slug

    @classmethod
    def make_unique_public_token(cls, instance_pk=None):
        while True:
            token = uuid.uuid4().hex[:8]
            if not cls.objects.filter(public_token=token).exclude(pk=instance_pk).exists():
                return token
