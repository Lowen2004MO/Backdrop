import os

from django.core.exceptions import ImproperlyConfigured

from people_pulse.cloud_secrets import get_secret_json, get_secret_string

from .base import *

MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')


def required(name):
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f'{name} must be set in the cloud environment.')
    return value


def required_or_secret(value_name, secret_arn_name):
    value = os.environ.get(value_name)
    if value:
        return value
    secret_arn = os.environ.get(secret_arn_name)
    if secret_arn:
        return get_secret_string(secret_arn)
    raise ImproperlyConfigured(
        f'{value_name} or {secret_arn_name} must be set in the cloud environment.'
    )


SECRET_KEY = required_or_secret(
    'DJANGO_SECRET_KEY',
    'DJANGO_SECRET_KEY_SECRET_ARN',
)
DEBUG = False
ALLOWED_HOSTS = [item.strip() for item in required('DJANGO_ALLOWED_HOSTS').split(',') if item.strip()]
CSRF_TRUSTED_ORIGINS = [
    item.strip() for item in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if item.strip()
]

database_secret_arn = os.environ.get('DB_SECRET_ARN')
database_secret = get_secret_json(database_secret_arn) if database_secret_arn else {}
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': required('DB_NAME'),
        'USER': database_secret.get('username') or required('DB_USER'),
        'PASSWORD': database_secret.get('password') or required('DB_PASSWORD'),
        'HOST': required('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {'sslmode': 'require'},
    }
}
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
if os.environ.get('DJANGO_HTTPS', '').lower() == 'true':
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO')},
}
