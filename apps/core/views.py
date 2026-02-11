"""Core views - 랜딩 페이지 및 안내 페이지"""
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.contrib import messages
from django.views.decorators.http import require_POST, require_http_methods

from .models import Suggestion


def landing_page(request):
    """랜딩 페이지 - 서버 위치 기준 계절/날씨 UI"""
    context = {
        'default_location': settings.DEFAULT_LOCATION,
    }
    return render(request, 'core/landing.html', context)


def guide_page(request):
    """사이트 안내 페이지"""
    return render(request, 'core/guide.html')


def mypage_guide(request):
    """마이페이지 시스템 안내 페이지"""
    return render(request, 'core/mypage_guide.html')


def default_location(request):
    """기본 위치 API (서버 위치 반환)"""
    return JsonResponse({
        'latitude': settings.DEFAULT_LOCATION['latitude'],
        'longitude': settings.DEFAULT_LOCATION['longitude'],
    })


@require_http_methods(["GET", "POST"])
def suggestion_form(request):
    """운영자에게 건의하기 폼"""
    if request.method == 'POST':
        category = request.POST.get('category', 'OTHER')
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        
        if not title or not content:
            messages.error(request, '제목과 내용을 입력해주세요.')
            return render(request, 'core/suggestion_form.html', {
                'categories': Suggestion.Category.choices,
            })
        
        suggestion_data = {
            'category': category,
            'title': title,
            'content': content,
        }
        
        if request.user.is_authenticated:
            suggestion_data['author'] = request.user
        else:
            guest_nickname = request.POST.get('guest_nickname', '익명').strip()
            email = request.POST.get('email', '').strip()
            suggestion_data['guest_nickname'] = guest_nickname or '익명'
            suggestion_data['email'] = email
        
        Suggestion.objects.create(**suggestion_data)
        messages.success(request, '건의사항이 성공적으로 접수되었습니다!')
        return redirect('core:suggestion_done')
    
    return render(request, 'core/suggestion_form.html', {
        'categories': Suggestion.Category.choices,
    })


def suggestion_done(request):
    """건의 완료 페이지"""
    return render(request, 'core/suggestion_done.html')
