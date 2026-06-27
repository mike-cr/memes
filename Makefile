PYTHON ?= python3
VENV ?= .venv
APP_USER ?= www-data
SERVICE ?= memevault

BIN := $(VENV)/bin
MANAGE := $(BIN)/python manage.py

.PHONY: help venv install migrate superuser run test check static update server-update restart status logs fix-static-ownership fix-runtime-ownership

help:
	@printf '%s\n' \
		'Targets:' \
		'  make install              Create venv, install dependencies, run migrations' \
		'  make run                  Start local Django development server' \
		'  make superuser            Create a Django admin/login user' \
		'  make test                 Run Django tests' \
		'  make check                Run Django system checks and migration drift check' \
		'  make static               Collect production static files' \
		'  make update               Pull, install dependencies, migrate, collect static' \
		'  make server-update        update + restart systemd service' \
		'  make restart              Restart systemd service, SERVICE=memevault by default' \
		'  make status               Show systemd service status' \
		'  make logs                 Tail recent service logs' \
		'  make fix-static-ownership Make staticfiles writable by the current deploy user' \
		'  make fix-runtime-ownership Make media/db writable by APP_USER=www-data'

venv:
	$(PYTHON) -m venv $(VENV)

install: venv
	$(BIN)/python -m pip install -r requirements.txt
	$(MANAGE) migrate

migrate:
	$(MANAGE) migrate

superuser:
	$(MANAGE) createsuperuser

run:
	$(MANAGE) runserver

test:
	$(MANAGE) test

check:
	$(MANAGE) check
	$(MANAGE) makemigrations --check --dry-run
	node --check static/library/app.js

static:
	$(MANAGE) collectstatic --noinput

update:
	git pull
	$(BIN)/python -m pip install -r requirements.txt
	$(MANAGE) migrate
	$(MANAGE) collectstatic --noinput

server-update: update restart

restart:
	sudo systemctl restart $(SERVICE)

status:
	sudo systemctl status $(SERVICE)

logs:
	sudo journalctl -u $(SERVICE) -n 100 --no-pager

fix-static-ownership:
	mkdir -p staticfiles
	sudo chown -R $$(id -un):$$(id -gn) staticfiles
	chmod -R a+rX staticfiles

fix-runtime-ownership:
	mkdir -p media
	sudo chown -R $(APP_USER):$(APP_USER) media
	@if [ -f db.sqlite3 ]; then sudo chown $(APP_USER):$(APP_USER) db.sqlite3; fi
