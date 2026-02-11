from django import template
from django.utils.translation import get_language

from apps.translations.services import get_translated_field, detect_source_language

register = template.Library()


def _get_translated(obj, field_name):
    """공통 번역 로직"""
    current_lang = get_language()
    if not current_lang:
        current_lang = 'ko'
    current_lang = current_lang[:2]

    original = getattr(obj, field_name, '')
    if not original:
        return ''

    source_lang = detect_source_language(original)
    if source_lang == current_lang:
        return original

    return get_translated_field(obj, field_name, current_lang)


@register.simple_tag
def translated_field(obj, field_name):
    """
    캐시된 번역 반환. 현재 언어가 원문 언어와 같으면 원문 반환.
    사용법: {% translated_field coordinate "title" %}
    """
    return _get_translated(obj, field_name)


@register.filter
def translate_field(obj, field_name):
    """
    필터 버전. 다른 필터와 체이닝 가능.
    사용법: {{ coordinate|translate_field:"title" }}
           {{ coordinate|translate_field:"description"|linebreaks }}
    """
    return _get_translated(obj, field_name)
