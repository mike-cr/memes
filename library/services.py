import ipaddress
import socket
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_BYTES = 12 * 1024 * 1024
THUMBNAIL_SIZE = (420, 420)
ALLOWED_SCHEMES = {'http', 'https'}
ALLOWED_FORMATS = {'JPEG', 'PNG', 'GIF', 'WEBP'}
TRANSPARENCY_FORMATS = {'PNG', 'WEBP'}


class ImageImportError(ValueError):
    pass


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ImageImportError('Only http and https URLs are allowed.')
    if not parsed.hostname:
        raise ImageImportError('The URL must include a host.')

    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ImageImportError('The URL host could not be resolved.') from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ImageImportError('URLs resolving to private or local networks are not allowed.')


def read_limited_upload(uploaded_file, limit=MAX_IMAGE_BYTES):
    data = bytearray()
    for chunk in uploaded_file.chunks():
        data.extend(chunk)
        if len(data) > limit:
            raise ImageImportError('Image is larger than the configured 12 MB limit.')
    return bytes(data)


def fetch_remote_image(url):
    validate_public_url(url)
    opener = build_opener(SafeRedirectHandler)
    request = Request(
        url,
        headers={
            'User-Agent': 'MemeVault/1.0',
            'Accept': 'image/avif,image/webp,image/png,image/jpeg,image/gif,*/*;q=0.5',
        },
    )

    try:
        with opener.open(request, timeout=8) as response:
            data = bytearray()
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_IMAGE_BYTES:
                    raise ImageImportError('Image is larger than the configured 12 MB limit.')
    except HTTPError as exc:
        raise ImageImportError(f'Image URL returned HTTP {exc.code}.') from exc
    except URLError as exc:
        raise ImageImportError('Image URL could not be fetched.') from exc
    except TimeoutError as exc:
        raise ImageImportError('Image URL timed out.') from exc

    return bytes(data)


def inspect_image(data):
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            if image.format not in ALLOWED_FORMATS:
                raise ImageImportError('Supported formats are JPEG, PNG, GIF, and WebP.')
            return {
                'format': image.format,
                'content_type': Image.MIME.get(image.format, 'application/octet-stream'),
                'width': image.width,
                'height': image.height,
            }
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageImportError('The file is not a valid image.') from exc


def strip_image_metadata(data, source_format):
    output_format = source_format if source_format in TRANSPARENCY_FORMATS else 'JPEG'
    with Image.open(BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image)
        save_kwargs = {}

        if output_format == 'JPEG':
            if image.mode not in ('RGB', 'L'):
                background = Image.new('RGB', image.size, 'white')
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.getchannel('A'))
                else:
                    background.paste(image.convert('RGB'))
                image = background
            else:
                image = image.convert('RGB')
            save_kwargs = {'quality': 92, 'optimize': True}
        elif output_format == 'PNG':
            image = image.convert('RGBA' if image.mode in ('RGBA', 'LA', 'P') else 'RGB')
            save_kwargs = {'optimize': True}
        elif output_format == 'WEBP':
            image = image.convert('RGBA' if image.mode in ('RGBA', 'LA', 'P') else 'RGB')
            save_kwargs = {'quality': 92, 'method': 6}

        output = BytesIO()
        image.save(output, format=output_format, **save_kwargs)
        return output.getvalue(), {
            'format': output_format,
            'content_type': Image.MIME.get(output_format, 'application/octet-stream'),
            'width': image.width,
            'height': image.height,
        }


def make_thumbnail(data):
    with Image.open(BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail(THUMBNAIL_SIZE)
        if image.mode not in ('RGB', 'L'):
            background = Image.new('RGB', image.size, 'white')
            if image.mode == 'RGBA':
                background.paste(image, mask=image.getchannel('A'))
            else:
                background.paste(image.convert('RGB'))
            image = background
        else:
            image = image.convert('RGB')

        output = BytesIO()
        image.save(output, format='JPEG', quality=82, optimize=True)
        return ContentFile(output.getvalue())


def extension_for_format(image_format):
    return {
        'JPEG': '.jpg',
        'PNG': '.png',
        'WEBP': '.webp',
    }.get(image_format, '.img')
