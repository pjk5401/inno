#!/usr/bin/env bash
set -euo pipefail
export DEBUG=1
python manage.py check
python manage.py makemigrations --check --dry-run
APP_ENV=live python manage.py test attendance --noinput
APP_ENV=sandbox python manage.py test attendance --noinput
python scripts/test_archive.py
python scripts/test_network_config.py
bash -n manage.sh deploy/init-db.sh
bash scripts/test_manage.sh

if command -v node >/dev/null 2>&1; then node scripts/test_checkin.cjs; fi
