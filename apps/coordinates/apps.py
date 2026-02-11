from django.apps import AppConfig


class CoordinatesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.coordinates'
    verbose_name = '좌표 관리'
    
    def ready(self):
        import apps.coordinates.signals  # noqa
