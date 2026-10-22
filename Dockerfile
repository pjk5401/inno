FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home app
COPY . .
RUN DEBUG=1 python manage.py collectstatic --noinput && mkdir -p /data/signatures && chown -R app:app /app /data
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "90", "--graceful-timeout", "30", "--max-requests", "1000", "--max-requests-jitter", "100", "--error-logfile", "-"]
