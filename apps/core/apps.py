from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = '코어'

    def ready(self):
        # 아이폰 HEIC 를 PIL 이 열 수 있게 등록한다.
        # 이게 없으면 아이폰 사진이 깨진 채로 저장된다.
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            import logging
            logging.getLogger(__name__).warning(
                'pillow-heif 가 없어 HEIC(아이폰 사진)를 못 연다')
