import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SANDBOX = os.getenv('APP_ENV', 'live') == 'sandbox'
# Keep guest attendance data/routes available, but hide its entry points by default.
GUEST_ATTENDANCE_VISIBLE = False
APP_LABEL = '테스트 환경' if SANDBOX else '출석 서비스'
URL_PREFIX = '/test' if SANDBOX else ''
DEBUG = os.getenv('DEBUG', '0') == '1'
SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG or 'test' in __import__('sys').argv:
        SECRET_KEY = 'local-development-only-never-use-in-production'
    else:
        raise RuntimeError('SECRET_KEY must be set. Run bash manage.sh for deployment.')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
PUBLIC_ORIGIN = os.getenv('PUBLIC_ORIGIN', 'http://127.0.0.1:8000').rstrip('/')
CSRF_TRUSTED_ORIGINS = [PUBLIC_ORIGIN]
CSRF_FAILURE_VIEW = 'attendance.views.csrf_failure'
INSTALLED_APPS = [
    'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
    'django.contrib.messages', 'django.contrib.staticfiles', 'attendance',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'attendance.middleware.ResponsePolicyMiddleware',
]
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
              'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
              'OPTIONS': {'context_processors': [
                  'django.template.context_processors.request',
                  'django.contrib.auth.context_processors.auth',
                  'django.contrib.messages.context_processors.messages',
                  'attendance.context.common',
              ]}}]
if os.getenv('DB_HOST'):
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql',
        'HOST': os.environ['DB_HOST'], 'PORT': os.getenv('DB_PORT', '5432'),
        'NAME': os.environ['DB_NAME'], 'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'], 'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True}}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / ('sandbox.sqlite3' if SANDBOX else 'local.sqlite3')}}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_TZ = True
STATIC_URL = URL_PREFIX + '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT', str(BASE_DIR / 'var' / ('test-signatures' if SANDBOX else 'signatures'))))
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = URL_PREFIX + '/staff/login/'
LOGIN_REDIRECT_URL = URL_PREFIX + '/staff/'
SESSION_COOKIE_NAME = 'attendance_test_session' if SANDBOX else 'attendance_session'
CSRF_COOKIE_NAME = 'attendance_test_csrf' if SANDBOX else 'attendance_csrf'
SESSION_COOKIE_PATH = URL_PREFIX + '/' if SANDBOX else '/'
CSRF_COOKIE_PATH = SESSION_COOKIE_PATH
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 8 * 3600
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
BROWSER_COOKIE_NAME = 'attendance_test_browser' if SANDBOX else 'attendance_browser'
BROWSER_COOKIE_AGE = 365 * 24 * 3600
X_FRAME_OPTIONS = 'DENY'
# Set only when the school proxy sanitizes this header and direct VM access is restricted.
if os.getenv('TRUST_PROXY_HTTPS', '0') == '1':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', '0') == '1'
SECURE_REDIRECT_EXEMPT = [r'^health/$', r'^test/health/$']
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 4 * 1024 * 1024
LOGGING = {'version': 1, 'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'}}
