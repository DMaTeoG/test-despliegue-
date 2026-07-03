import os
import dj_database_url
from .base import *

DEBUG = False

# Permitir el dominio de Render y localhost
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

# Configuración de Base de Datos PostgreSQL usando DATABASE_URL de Render
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Habilitar WhiteNoise para archivos estáticos (se inserta justo después de SecurityMiddleware)
if 'django.middleware.security.SecurityMiddleware' in MIDDLEWARE:
    MIDDLEWARE.insert(
        MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
        'whitenoise.middleware.WhiteNoiseMiddleware'
    )
else:
    MIDDLEWARE.insert(0, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Configuración de Archivos Estáticos para Producción
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Seguridad SSL en producción
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
