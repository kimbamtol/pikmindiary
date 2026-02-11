"""번역 핵심 서비스 - DeepL API 호출 + 번역 캐시 관리"""
import logging
import requests
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from .models import ContentTranslation

logger = logging.getLogger(__name__)

SUPPORTED_LANGS = ['ko', 'ja', 'en']

# DeepL API 언어 코드 매핑
DEEPL_LANG_MAP = {
    'ko': 'KO',
    'ja': 'JA',
    'en': 'EN',
}


def detect_source_language(text):
    """간단한 언어 감지 - 한글/일본어/영어 판별"""
    if not text:
        return 'ko'

    korean_count = 0
    japanese_count = 0
    latin_count = 0

    for char in text:
        cp = ord(char)
        # 한글 음절 + 자모
        if 0xAC00 <= cp <= 0xD7AF or 0x3130 <= cp <= 0x318F:
            korean_count += 1
        # 히라가나 + 카타카나 + CJK (일본 한자 포함)
        elif 0x3040 <= cp <= 0x30FF or 0x31F0 <= cp <= 0x31FF:
            japanese_count += 1
        # 라틴 문자
        elif 0x0041 <= cp <= 0x005A or 0x0061 <= cp <= 0x007A:
            latin_count += 1

    total = korean_count + japanese_count + latin_count
    if total == 0:
        return 'ko'

    if korean_count > japanese_count and korean_count > latin_count:
        return 'ko'
    elif japanese_count > korean_count and japanese_count > latin_count:
        return 'ja'
    else:
        return 'en'


def call_deepl_api(text, source_lang, target_lang):
    """DeepL API 호출"""
    api_key = settings.DEEPL_API_KEY
    api_url = settings.DEEPL_API_URL

    if not api_key or api_key == 'your-deepl-api-key':
        logger.warning("DeepL API key not configured")
        return None

    try:
        response = requests.post(
            api_url,
            data={
                'auth_key': api_key,
                'text': text,
                'source_lang': DEEPL_LANG_MAP.get(source_lang, source_lang.upper()),
                'target_lang': DEEPL_LANG_MAP.get(target_lang, target_lang.upper()),
            },
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
        translations = result.get('translations', [])
        if translations:
            return translations[0].get('text', '')
        return None
    except Exception as e:
        logger.error(f"DeepL API error: {e}")
        return None


def translate_on_create(obj, fields):
    """새 게시글 작성 시 호출. 다른 2개 언어로 즉시 번역 & DB 저장."""
    if not fields:
        return

    # 첫 번째 필드로 원문 언어 감지
    first_text = getattr(obj, fields[0], '')
    source_lang = detect_source_language(first_text)
    target_langs = [l for l in SUPPORTED_LANGS if l != source_lang]

    ct = ContentType.objects.get_for_model(obj)

    for field in fields:
        text = getattr(obj, field, '')
        if not text:
            continue

        for target in target_langs:
            translated = call_deepl_api(text, source_lang, target)
            if translated:
                ContentTranslation.objects.update_or_create(
                    content_type=ct,
                    object_id=obj.pk,
                    field_name=field,
                    target_language=target,
                    defaults={
                        'source_language': source_lang,
                        'translated_text': translated,
                    }
                )


def get_translated_field(obj, field_name, target_lang):
    """캐시된 번역 조회. 없으면 원문 반환."""
    original = getattr(obj, field_name, '')
    if not original:
        return ''

    source_lang = detect_source_language(original)
    if source_lang == target_lang:
        return original

    ct = ContentType.objects.get_for_model(obj)
    try:
        translation = ContentTranslation.objects.get(
            content_type=ct,
            object_id=obj.pk,
            field_name=field_name,
            target_language=target_lang,
        )
        return translation.translated_text
    except ContentTranslation.DoesNotExist:
        return original
