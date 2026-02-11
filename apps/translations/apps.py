from django.apps import AppConfig


class TranslationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.translations'
    verbose_name = '번역'

    def ready(self):
        import apps.translations.signals  # noqa
