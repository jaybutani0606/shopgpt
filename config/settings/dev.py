from .base import *

# SECURITY WARNING: keep the secret key used in development!
SECRET_KEY = 'django-insecure-dev-secret-key-placeholder'

DEBUG = True

ALLOWED_HOSTS = ['*']

# Email settings for development/testing
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

