"""Accounts views - 마이페이지"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

from .models import CustomUser
from apps.coordinates.models import Coordinate
from apps.interactions.models import Bookmark
from apps.core.models import Suggestion
from apps.comments.models import Comment


@login_required
def my_page(request):
    """마이페이지 메인"""
    user = request.user
    
    # 통계
    my_posts = Coordinate.objects.filter(author=user)
    approved_count = my_posts.filter(status=Coordinate.Status.APPROVED).count()
    pending_count = my_posts.filter(status=Coordinate.Status.PENDING).count()
    bookmark_count = Bookmark.objects.filter(user=user).count()
    
    # 최근 글 5개
    recent_posts = my_posts.order_by('-created_at')[:5]
    
    # 건의사항 (최근 3개)
    my_suggestions = Suggestion.objects.filter(author=user).order_by('-created_at')[:3]
    unread_replies = Suggestion.objects.filter(
        author=user, 
        admin_reply__isnull=False
    ).exclude(admin_reply='').count()
    
    context = {
        'approved_count': approved_count,
        'pending_count': pending_count,
        'bookmark_count': bookmark_count,
        'recent_posts': recent_posts,
        'total_likes_received': user.total_likes_received,
        'my_suggestions': my_suggestions,
        'unread_replies': unread_replies,
    }
    return render(request, 'accounts/my_page.html', context)


@login_required
def my_posts(request):
    """내가 쓴 글 목록"""
    status_filter = request.GET.get('status', '')
    posts = Coordinate.objects.filter(author=request.user)
    
    if status_filter:
        posts = posts.filter(status=status_filter)
    
    posts = posts.order_by('-created_at')
    
    paginator = Paginator(posts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
    }
    return render(request, 'accounts/my_posts.html', context)


@login_required
def my_bookmarks(request):
    """북마크한 글 목록"""
    bookmarks = Bookmark.objects.filter(user=request.user).select_related('coordinate')
    
    # 승인된 글만 표시
    bookmarked_coordinates = [
        b.coordinate for b in bookmarks 
        if b.coordinate.status == Coordinate.Status.APPROVED
    ]
    
    paginator = Paginator(bookmarked_coordinates, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'accounts/my_bookmarks.html', context)


@login_required
def my_settings(request):
    """계정 설정"""
    from .constants import PIKMIN_EMOJIS

    if request.method == 'POST':
        user = request.user
        user.nickname = request.POST.get('nickname', user.nickname)
        user.bio = request.POST.get('bio', user.bio)

        if 'profile_image' in request.FILES:
            user.profile_image = request.FILES['profile_image']

        # 이모지 설정 (랭킹 등록 사용자만)
        if user.has_ranking():
            emoji = request.POST.get('profile_emoji', '')
            # 허용된 이모지인지 검증
            if emoji in PIKMIN_EMOJIS or emoji == '':
                user.profile_emoji = emoji

        # 칭호 선택 (랭커 또는 관리자)
        selected_title = request.POST.get('selected_title', '')
        if selected_title == '' or user.can_select_title(selected_title):
            user.selected_title = selected_title

        # 배지 커스터마이즈 (랭커 또는 관리자)
        if user.can_customize_badge():
            badge_style = request.POST.get('badge_style', '')
            if badge_style in dict(user.BadgeStyle.choices) and user.can_use_style(badge_style):
                user.badge_style = badge_style

            nickname_color = request.POST.get('nickname_color', '')
            if nickname_color == '' or (nickname_color in dict(user.ColorChoice.choices) and user.can_use_color(nickname_color)):
                user.nickname_color = nickname_color

            title_color = request.POST.get('title_color', '')
            if title_color == '' or (title_color in dict(user.ColorChoice.choices) and user.can_use_color(title_color)):
                user.title_color = title_color

            nickname_bg_color = request.POST.get('nickname_bg_color', '')
            if nickname_bg_color == '' or (nickname_bg_color in dict(user.ColorChoice.choices) and user.can_use_color(nickname_bg_color)):
                user.nickname_bg_color = nickname_bg_color

        user.save()

    # 선택 가능한 칭호 목록
    available_titles = request.user.get_available_titles()
    ranking_position = request.user.get_ranking_position()
    can_customize = request.user.can_customize_badge()

    context = {
        'pikmin_emojis': PIKMIN_EMOJIS,
        'available_titles': available_titles,
        'ranking_position': ranking_position,
        'can_customize': can_customize,
        'badge_styles': request.user.get_available_styles() if can_customize else [],
        'color_choices': request.user.get_available_colors() if can_customize else [],
    }
    return render(request, 'accounts/my_settings.html', context)


def user_profile(request, user_id):
    """유저 프로필 (공개)"""
    user = get_object_or_404(CustomUser, pk=user_id)

    # 승인된 글만
    approved_posts = Coordinate.objects.filter(
        author=user,
        status=Coordinate.Status.APPROVED
    ).order_by('-created_at')

    # 통계 계산 (실시간)
    from apps.interactions.models import Like
    from django.db.models import Sum

    total_posts = approved_posts.count()
    total_likes = Like.objects.filter(coordinate__author=user, coordinate__status=Coordinate.Status.APPROVED).count()

    # 최근 작성한 글
    recent_posts = approved_posts[:10]

    # 최근 댓글
    recent_comments = Comment.objects.filter(
        author=user,
        is_deleted=False
    ).select_related('coordinate', 'farming_journal').order_by('-created_at')[:10]

    # 농사 일지
    from apps.farming.models import FarmingJournal
    farming_journals = FarmingJournal.objects.filter(author=user).order_by('-created_at')[:5]

    context = {
        'profile_user': user,
        'posts': recent_posts,
        'recent_comments': recent_comments,
        'farming_journals': farming_journals,
        'total_posts': total_posts,
        'total_likes': total_likes,
    }
    return render(request, 'accounts/user_profile.html', context)


@login_required
def my_suggestions(request):
    """내 건의사항 목록"""
    suggestions = Suggestion.objects.filter(author=request.user).order_by('-created_at')

    paginator = Paginator(suggestions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'accounts/my_suggestions.html', context)


@login_required
def my_comments(request):
    """내가 남긴 댓글 목록"""
    comments = Comment.objects.filter(
        author=request.user,
        is_deleted=False
    ).select_related('coordinate', 'farming_journal').order_by('-created_at')

    paginator = Paginator(comments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'accounts/my_comments.html', context)
