import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Meme, Tag
from .services import ImageImportError, validate_public_url
from .views import MEME_PAGE_SIZE


def image_bytes(fmt='PNG', size=(16, 16), color=(20, 108, 100)):
    output = BytesIO()
    Image.new('RGB', size, color).save(output, format=fmt)
    return output.getvalue()


def image_with_exif_bytes():
    image = Image.new('RGB', (16, 16), (20, 108, 100))
    exif = Image.Exif()
    exif[0x010F] = 'Identifying Camera'
    exif[0x0110] = 'Identifying Model'
    output = BytesIO()
    image.save(output, format='JPEG', exif=exif)
    return output.getvalue()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class MemeLibraryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='mike',
            password='correct horse battery staple',
        )

    def login(self):
        self.client.login(username='mike', password='correct horse battery staple')

    def test_index_requires_login(self):
        response = self.client.get(reverse('library:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_upload_creates_meme_thumbnail_and_tags(self):
        self.login()
        upload = SimpleUploadedFile('joke.png', image_bytes(), content_type='image/png')

        response = self.client.post(
            reverse('library:create'),
            {
                'title': 'A joke',
                'tags': 'cats, reaction, cats',
                'image': upload,
            },
        )

        self.assertEqual(response.status_code, 302)
        meme = Meme.objects.get()
        self.assertEqual(meme.title, 'A joke')
        self.assertEqual(sorted(meme.tags.values_list('name', flat=True)), ['cats', 'reaction'])
        self.assertTrue(Path(meme.original.path).exists())
        self.assertTrue(Path(meme.thumbnail.path).exists())

    def test_download_filename_prefers_title(self):
        self.login()
        upload = SimpleUploadedFile('original-camera-name.png', image_bytes(), content_type='image/png')
        self.client.post(
            reverse('library:create'),
            {'title': 'Funny Cat Reaction', 'image': upload},
        )

        meme = Meme.objects.get()
        self.assertEqual(meme.download_filename, 'funny-cat-reaction.png')
        self.assertRegex(meme.public_url(), r'^/i/[0-9a-f]{8}/funny-cat-reaction\.png$')
        self.assertEqual(meme.public_url().rsplit('/', 1)[1], 'funny-cat-reaction.png')
        self.assertNotIn(str(meme.public_id), meme.public_url())

    def test_duplicate_titles_get_unique_name_links_with_short_tokens(self):
        self.login()
        first = SimpleUploadedFile('first.png', image_bytes(), content_type='image/png')
        second = SimpleUploadedFile('second.png', image_bytes(), content_type='image/png')
        self.client.post(reverse('library:create'), {'title': 'Same Name', 'image': first})
        self.client.post(reverse('library:create'), {'title': 'Same Name', 'image': second})

        urls = sorted(meme.public_url() for meme in Meme.objects.all())
        self.assertCountEqual([url.rsplit('/', 1)[1] for url in urls], ['same-name-2.png', 'same-name.png'])
        for meme in Meme.objects.all():
            self.assertRegex(meme.public_url(), r'^/i/[0-9a-f]{8}/same-name(-2)?\.png$')
            self.assertNotIn(str(meme.public_id), meme.public_url())

    def test_blank_title_does_not_preserve_original_filename(self):
        self.login()
        upload = SimpleUploadedFile('very-identifying-original-name.jpg', image_bytes('JPEG'), content_type='image/jpeg')
        self.client.post(reverse('library:create'), {'image': upload})

        meme = Meme.objects.get()
        self.assertNotIn('very-identifying-original-name', meme.original.name)
        self.assertNotIn('very-identifying-original-name', meme.download_filename)
        self.assertNotIn('very-identifying-original-name', meme.public_url())
        self.assertRegex(meme.public_url(), r'^/i/[0-9a-f]{8}/meme\.jpg$')

    def test_upload_strips_exif_metadata_from_saved_original(self):
        self.login()
        upload = SimpleUploadedFile('private.jpg', image_with_exif_bytes(), content_type='image/jpeg')
        self.client.post(
            reverse('library:create'),
            {'title': 'Private Metadata', 'image': upload},
        )

        meme = Meme.objects.get()
        with Image.open(meme.original.path) as saved:
            self.assertEqual(dict(saved.getexif()), {})
            self.assertEqual(saved.info.get('comment'), None)
        self.assertEqual(meme.content_type, 'image/jpeg')

    def test_tag_search_is_authenticated_and_live_searchable(self):
        Tag.objects.create(name='reaction')
        unauthenticated = self.client.get(reverse('library:tag_search_api'), {'q': 'rea'})
        self.assertEqual(unauthenticated.status_code, 302)

        self.login()
        response = self.client.get(reverse('library:tag_search_api'), {'q': 'rea'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['tags'][0]['name'], 'reaction')

    def test_editing_existing_meme_tags_updates_tags(self):
        self.login()
        upload = SimpleUploadedFile('edit-tags.png', image_bytes(), content_type='image/png')
        self.client.post(
            reverse('library:create'),
            {'title': 'Editable', 'image': upload, 'tags': 'old'},
        )
        meme = Meme.objects.get()

        response = self.client.post(
            reverse('library:edit', kwargs={'pk': meme.pk}),
            {'title': 'Editable', 'tags': 'new, reaction'},
        )

        self.assertEqual(response.status_code, 302)
        meme.refresh_from_db()
        self.assertEqual(sorted(meme.tags.values_list('name', flat=True)), ['new', 'reaction'])

    def test_editing_legacy_meme_with_blank_public_token_repairs_it(self):
        self.login()
        meme = Meme.objects.create(title='Legacy')
        Meme.objects.filter(pk=meme.pk).update(public_token='')

        response = self.client.post(
            reverse('library:edit', kwargs={'pk': meme.pk}),
            {'title': 'Legacy', 'tags': 'fixed'},
        )

        self.assertEqual(response.status_code, 302)
        meme.refresh_from_db()
        self.assertRegex(meme.public_url(), r'^/i/[0-9a-f]{8}/legacy\.img$')

    def test_public_image_is_available_without_login_but_index_is_not(self):
        self.login()
        upload = SimpleUploadedFile('share.png', image_bytes(), content_type='image/png')
        self.client.post(reverse('library:create'), {'image': upload, 'tags': 'share'})
        meme = Meme.objects.get()
        self.client.logout()

        response = self.client.get(meme.public_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

        index_response = self.client.get(reverse('library:index'))
        self.assertEqual(index_response.status_code, 302)

    def test_search_api_matches_tags(self):
        self.login()
        upload = SimpleUploadedFile('find.png', image_bytes(), content_type='image/png')
        self.client.post(reverse('library:create'), {'image': upload, 'tags': 'surprised'})

        response = self.client.get(reverse('library:meme_search_api'), {'q': 'surprised'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['memes']), 1)

    def test_meme_search_api_is_paginated(self):
        self.login()
        for index in range(MEME_PAGE_SIZE + 3):
            Meme.objects.create(title=f'Paged meme {index}')

        first = self.client.get(reverse('library:meme_search_api'), {'page': 1})
        second = self.client.get(reverse('library:meme_search_api'), {'page': 2})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(first.json()['memes']), MEME_PAGE_SIZE)
        self.assertEqual(first.json()['total'], MEME_PAGE_SIZE + 3)
        self.assertTrue(first.json()['hasNext'])
        self.assertEqual(first.json()['nextPage'], 2)
        self.assertEqual(len(second.json()['memes']), 3)
        self.assertFalse(second.json()['hasNext'])

    @patch('library.services.socket.getaddrinfo')
    def test_url_import_rejects_private_networks(self, getaddrinfo):
        getaddrinfo.return_value = [
            (None, None, None, None, ('127.0.0.1', 80)),
        ]

        with self.assertRaises(ImageImportError):
            validate_public_url('http://example.test/image.png')

# Create your tests here.
