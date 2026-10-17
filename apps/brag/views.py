"""Brag views - 피크민 자랑"""
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import BragLike, BragPost

PAGE_SIZE = 24
MAX_IMAGE_SIZE = 8 * 1024 * 1024
ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']


# ===== 헬퍼 =====

def _session_key(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def _liked_post_ids(request, posts):
    """현재 사용자가 좋아요한 글 id 집합"""
    ids = [p.pk for p in posts]
    if not ids:
        return set()
    qs = BragLike.objects.filter(post_id__in=ids)
    if request.user.is_authenticated:
        qs = qs.filter(user=request.user)
    else:
        key = request.session.session_key
        if not key:
            return set()
        qs = qs.filter(user__isnull=True, session_key=key)
    return set(qs.values_list('post_id', flat=True))


def _can_manage(request, post):
    """본인 글인지 (회원: 계정, 비회원: 비밀번호 확인 전 단계)"""
    if post.author:
        return request.user.is_authenticated and post.author == request.user
    return True  # 비회원 글은 비밀번호로 확인


def _validate_image(image):
    if not image:
        return _('사진을 선택해주세요.')
    if image.size > MAX_IMAGE_SIZE:
        return _('사진 파일 크기는 8MB를 초과할 수 없습니다.')
    if getattr(image, 'content_type', None) not in ALLOWED_TYPES:
        return _('허용되지 않는 파일 형식입니다. (JPG, PNG, WEBP, GIF만 가능)')
    return None


# ===== 목록 =====

def brag_list(request):
    """자랑 목록 - 사진 그리드"""
    sort = request.GET.get('sort', 'latest')
    queryset = BragPost.objects.filter(is_hidden=False).select_related('author')

    if sort == 'likes':
        queryset = queryset.order_by('-like_count', '-created_at')
    elif sort == 'comments':
        queryset = queryset.order_by('-comment_count', '-created_at')
    else:
        sort = 'latest'
        queryset = queryset.order_by('-created_at')

    paginator = Paginator(queryset, PAGE_SIZE)
    page = paginator.get_page(request.GET.get('page'))

    top = BragPost.current_top()

    context = {
        'posts': page.object_list,
        'week_groups': _group_by_week(page.object_list) if sort == 'latest' else None,
        'page_obj': page,
        'sort': sort,
        'total_count': paginator.count,
        'liked_ids': _liked_post_ids(request, page.object_list),
        'weekly_top': top['post'],
        'weekly_top_label': top['label'],
        'past_winners': BragPost.past_winners() if page.number == 1 else [],
    }
    return render(request, 'brag/list.html', context)


def _group_by_week(posts):
    """최신순 목록을 주차(월~일)별로 묶는다"""
    from collections import OrderedDict
    from datetime import timedelta

    this_week = BragPost.week_start()
    groups = OrderedDict()
    for post in posts:
        start = BragPost.week_start(post.created_at)
        groups.setdefault(start, []).append(post)

    out = []
    for start, items in groups.items():
        if start == this_week:
            label = '이번 주'
        elif start == this_week - timedelta(days=7):
            label = '지난주'
        else:
            label = None
        out.append({
            'start': start,
            'end': start + timedelta(days=6),
            'label': label,
            'posts': items,
        })
    return out


def brag_detail(request, pk):
    """자랑 글 상세 - 사진 + 댓글"""
    post = get_object_or_404(BragPost.objects.select_related('author'), pk=pk)
    if post.is_hidden and not (request.user.is_authenticated and request.user.is_staff):
        messages.error(request, _('숨김 처리된 글입니다.'))
        return redirect('brag:list')

    BragPost.objects.filter(pk=pk).update(view_count=post.view_count + 1)

    from apps.comments.models import Comment
    comments = Comment.objects.filter(
        brag_post=post, is_deleted=False, parent__isnull=True
    ).select_related('author').prefetch_related('replies', 'replies__author')

    context = {
        'post': post,
        'comments': comments,
        'liked': post.pk in _liked_post_ids(request, [post]),
        'is_owner': bool(post.author and request.user.is_authenticated and post.author == request.user),
    }
    return render(request, 'brag/detail.html', context)


# ===== 작성 / 삭제 =====

def brag_create(request):
    """자랑 글 올리기 (비회원 가능)"""
    if request.method != 'POST':
        return render(request, 'brag/create.html')

    image = request.FILES.get('image')
    error = _validate_image(image)
    if error:
        messages.error(request, error)
        return render(request, 'brag/create.html', {'caption': request.POST.get('caption', '')})

    caption = request.POST.get('caption', '').strip()[:200]
    watermark = request.POST.get('watermark') == 'on'

    post = BragPost(image=image, caption=caption, watermark_enabled=watermark)

    if request.user.is_authenticated:
        post.author = request.user
    else:
        nickname = request.POST.get('guest_nickname', '').strip()
        password = request.POST.get('guest_password', '')
        if not nickname or not password:
            messages.error(request, _('비회원은 닉네임과 비밀번호를 입력해야 합니다.'))
            return render(request, 'brag/create.html', {'caption': caption})
        post.guest_nickname = nickname[:30]
        post.guest_password = make_password(password)

    post.save()
    messages.success(request, _('자랑 글이 올라갔습니다!'))
    return redirect('brag:detail', pk=post.pk)


def brag_delete(request, pk):
    """자랑 글 삭제 - 회원은 본인, 비회원은 비밀번호"""
    post = get_object_or_404(BragPost, pk=pk)

    if post.author:
        if not (request.user.is_authenticated and post.author == request.user):
            messages.error(request, _('본인 글만 삭제할 수 있습니다.'))
            return redirect('brag:detail', pk=pk)
        if request.method == 'POST':
            post.delete()
            messages.success(request, _('삭제되었습니다.'))
            return redirect('brag:list')
        return render(request, 'brag/delete_confirm.html', {'post': post})

    # 비회원 글
    if request.method == 'POST':
        password = request.POST.get('password', '')
        if not check_password(password, post.guest_password):
            messages.error(request, _('비밀번호가 일치하지 않습니다.'))
            return render(request, 'brag/delete_confirm.html', {'post': post})
        post.delete()
        messages.success(request, _('삭제되었습니다.'))
        return redirect('brag:list')
    return render(request, 'brag/delete_confirm.html', {'post': post})


# ===== 좋아요 =====

@require_POST
def toggle_brag_like(request, pk):
    """좋아요 토글 (비회원 포함, 본인 글 제외)"""
    post = get_object_or_404(BragPost, pk=pk)

    if request.user.is_authenticated and post.author == request.user:
        return JsonResponse({'error': _('본인 글에는 좋아요를 누를 수 없습니다.')}, status=400)

    if request.user.is_authenticated:
        like = BragLike.objects.filter(post=post, user=request.user).first()
        if like:
            like.delete()
            liked = False
        else:
            BragLike.objects.create(post=post, user=request.user)
            liked = True
    else:
        key = _session_key(request)
        like = BragLike.objects.filter(post=post, user__isnull=True, session_key=key).first()
        if like:
            like.delete()
            liked = False
        else:
            BragLike.objects.create(post=post, session_key=key)
            liked = True

    count = BragLike.objects.filter(post=post).count()
    BragPost.objects.filter(pk=post.pk).update(like_count=count)

    # 회원이 다른 회원 글에 좋아요를 누르면 알림
    if liked and request.user.is_authenticated and post.author and post.author != request.user:
        from apps.interactions.models import Notification
        Notification.objects.create(
            recipient=post.author,
            actor=request.user,
            notification_type=Notification.NotificationType.LIKE,
            message=_("%(name)s님이 자랑한 사진에 ❤️ 좋아요를 눌렀어요") % {'name': request.user.nickname},
        )

    return JsonResponse({'liked': liked, 'like_count': count})


# ===== 댓글 =====

@require_POST
def brag_comment(request, pk):
    """자랑 글에 댓글 달기 (댓글 기능은 기존 것을 그대로 사용)"""
    from apps.comments.models import Comment
    from apps.comments.views import _create_comment, _validate_photo
    from apps.interactions.models import Notification

    post = get_object_or_404(BragPost, pk=pk)
    content = request.POST.get('content', '').strip()
    photo = request.FILES.get('photo')

    if not content and not photo:
        messages.error(request, _('댓글 내용이나 사진 중 하나는 입력해주세요.'))
        return redirect('brag:detail', pk=pk)

    photo_error = _validate_photo(photo)
    if photo_error:
        messages.error(request, photo_error)
        return redirect('brag:detail', pk=pk)

    parent = None
    parent_id = request.POST.get('parent_id')
    if parent_id:
        parent = Comment.objects.filter(pk=parent_id, brag_post=post).first()

    comment, actor_name, actor = _create_comment(
        request, content, photo=photo, parent=parent, brag_post=post
    )
    if comment is None:
        messages.error(request, actor_name)
        return redirect('brag:detail', pk=pk)

    post.comment_count = Comment.objects.filter(brag_post=post, is_deleted=False).count()
    post.save(update_fields=['comment_count'])

    if post.author and post.author != actor:
        Notification.objects.create(
            recipient=post.author,
            actor=actor,
            notification_type=Notification.NotificationType.COMMENT,
            message=_("%(name)s님이 자랑한 사진에 💬 댓글을 남겼어요") % {'name': actor_name},
        )

    return redirect('brag:detail', pk=pk)
