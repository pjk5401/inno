#!/usr/bin/env bash
set -euo pipefail
export DEBUG=1
python manage.py check
python manage.py makemigrations --check --dry-run
APP_ENV=live python manage.py test attendance --noinput
APP_ENV=sandbox python manage.py test attendance --noinput
python scripts/test_archive.py
bash -n manage.sh deploy/init-db.sh
