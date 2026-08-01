from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'integrations'

    def ready(self):
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured
        provider = getattr(settings, 'PRODUCT_API_PROVIDER', 'null')
        key = getattr(settings, 'PRODUCT_API_KEY', '')
        # Ignore checking during migrations, test setups or if provider is null
        # We check if provider is not null and no key is set
        if provider != 'null' and not key:
            raise ImproperlyConfigured(
                f"PRODUCT_API_PROVIDER is set to '{provider}', but PRODUCT_API_KEY setting is missing or empty."
            )

