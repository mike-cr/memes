# MemeVault

A small private meme organizer with public, unlisted direct image links.

## Stack

- Django 5.2 LTS for auth, sessions, CSRF, ORM, migrations, and secure defaults.
- SQLite for local/small deployments. Move to Postgres if write concurrency or data size grows.
- Pillow for image validation and thumbnail generation.
- Vanilla JavaScript for live search/tag editing without a frontend build step.

## Setup

```sh
make install
make superuser
make run
```

Open `http://127.0.0.1:8000/` and sign in with the superuser account.

## Production Notes

Set these environment variables in production:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`, comma-separated
- `DJANGO_DEBUG=false`
- `DJANGO_CSRF_TRUSTED_ORIGINS`, comma-separated HTTPS origins if needed

Use a real WSGI/ASGI server such as Gunicorn behind a reverse proxy. Keep `media/` private except for this app's public `/i/<short-token>/<generated-filename>` route so images are shareable but not browseable as a directory.

## Common Commands

```sh
make test
make check
make static
make server-update
```

On a server where the deploy user owns the source tree and `www-data` runs the app, these targets repair the usual writable paths:

```sh
make fix-static-ownership
make fix-runtime-ownership
```
