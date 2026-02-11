from django.contrib import admin
from .models import ContentTranslation


@admin.register(ContentTranslation)
class ContentTranslationAdmin(admin.ModelAdmin):
    list_display = ['content_type', 'object_id', 'field_name', 'source_language', 'target_language', 'updated_at']
    list_filter = ['source_language', 'target_language', 'content_type']
    search_fields = ['translated_text']
    readonly_fields = ['created_at', 'updated_at']
