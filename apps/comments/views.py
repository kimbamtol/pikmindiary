"""Comments views - 댓글"""
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.hashers import make_password, check_password

from .models import Comment
from apps.coordinates.models import Coordinate
from apps.interactions.models import Notification


# ===== 헬퍼 함수 =====

def _validate_photo(photo):
    """사진 파일 검증. 오류 시 메시지 문자열 반환, 정상이면 None"""
    if not photo:
        return None
    if photo.size > 5 * 1024 * 1024:
        return '사진 파일 크기는 5MB를 초과할 수 없습니다.'
    allowed_types = ['image/jpeg', 'image/png', 'image/webp']
    if photo.content_type not in allowed_types:
        return '허용되지 않는 파일 형식입니다. (JPG, PNG, WEBP만 가능)'
    return None


def _create_comment(request, content, photo=None, parent=None, coordinate=None, farming_journal=None):
    """회원/비회원 댓글 생성 공통 로직. (comment, actor_name, actor) 튜플 반환. 실패 시 (None, error_msg, None)"""
    kwargs = {
        'content': content,
        'photo': photo,
        'parent': parent,
        'coordinate': coordinate,
        'farming_journal': farming_journal,
    }

    if request.user.is_authenticated:
        kwargs['author'] = request.user
        comment = Comment.objects.create(**kwargs)
        return comment, request.user.nickname, request.user
    else:
        guest_nickname = request.POST.get('guest_nickname', '익명')
        guest_password = request.POST.get('guest_password', '')
        if not guest_password:
            return None, '비회원은 비밀번호를 입력해야 합니다.', None
        kwargs['guest_nickname'] = guest_nickname
        kwargs['guest_password'] = make_password(guest_password)
        comment = Comment.objects.create(**kwargs)
        return comment, guest_nickname, None


def _update_comment_count(coordinate=None, farming_journal=None):
    """댓글 수 캐시 업데이트"""
    if coordinate:
        coordinate.comment_count = Comment.objects.filter(
            coordinate=coordinate, is_deleted=False
        ).count()
        coordinate.save(update_fields=['comment_count'])
    elif farming_journal and hasattr(farming_journal, 'comment_count'):
        farming_journal.comment_count = Comment.objects.filter(
            farming_journal=farming_journal, is_deleted=False
        ).count()
        farming_journal.save(update_fields=['comment_count'])


# ===== 좌표 댓글 =====

@require_POST
def comment_create(request, coordinate_id):
    """댓글 작성"""
    coordinate = get_object_or_404(Coordinate, pk=coordinate_id)
    content = request.POST.get('content', '').strip()
    photo = request.FILES.get('photo')

    if not content and not photo:
        messages.error(request, '댓글 내용이나 사진 중 하나는 입력해주세요.')
        return redirect('coordinates:detail', pk=coordinate_id)

    photo_error = _validate_photo(photo)
    if photo_error:
        messages.error(request, photo_error)
        return redirect('coordinates:detail', pk=coordinate_id)

    comment, actor_name, actor = _create_comment(
        request, content, photo=photo, coordinate=coordinate
    )
    if comment is None:
        messages.error(request, actor_name)  # actor_name은 에러 메시지
        return redirect('coordinates:detail', pk=coordinate_id)

    # 알림 생성
    if coordinate.author and coordinate.author != actor:
        emoji = '📷' if photo else '💬'
        Notification.objects.create(
            recipient=coordinate.author,
            actor=actor,
            notification_type=Notification.NotificationType.COMMENT,
            coordinate=coordinate,
            message=f"{actor_name}님이 '{coordinate.title}'에 {emoji} 댓글을 남겼어요"
        )

    _update_comment_count(coordinate=coordinate)

    if request.headers.get('HX-Request'):
        from django.template.loader import render_to_string
        comments = Comment.objects.filter(
            coordinate=coordinate, is_deleted=False, parent__isnull=True
        ).select_related('author').prefetch_related('replies')
        html = render_to_string('comments/_comment_list.html', {
            'comments': comments,
            'coordinate': coordinate,
        }, request=request)
        return JsonResponse({'html': html})

    messages.success(request, '댓글이 등록되었습니다.')
    return redirect('coordinates:detail', pk=coordinate_id)


@require_POST
def comment_edit(request, pk):
    """댓글 수정"""
    comment = get_object_or_404(Comment, pk=pk)
    coordinate_id = comment.coordinate.pk

    can_edit = False
    if request.user.is_authenticated and comment.author == request.user:
        can_edit = True
    elif comment.guest_password:
        password = request.POST.get('password', '')
        if check_password(password, comment.guest_password):
            can_edit = True

    if not can_edit:
        messages.error(request, '수정 권한이 없습니다.')
        return redirect('coordinates:detail', pk=coordinate_id)

    content = request.POST.get('content', '').strip()
    if content:
        comment.content = content
        comment.save()
        messages.success(request, '댓글이 수정되었습니다.')

    return redirect('coordinates:detail', pk=coordinate_id)


@require_POST
def comment_delete(request, pk):
    """댓글 삭제 (소프트 삭제)"""
    comment = get_object_or_404(Comment, pk=pk)

    # 리디렉션 URL 결정
    if comment.coordinate:
        redirect_url = ('coordinates:detail', comment.coordinate.pk)
    elif comment.farming_journal:
        redirect_url = ('farming:journal_detail', comment.farming_journal.pk)
    else:
        redirect_url = ('core:landing', None)

    can_delete = False
    if request.user.is_authenticated:
        if comment.author == request.user or request.user.is_staff:
            can_delete = True

    if not can_delete and comment.guest_password:
        password = request.POST.get('password', '')
        if check_password(password, comment.guest_password):
            can_delete = True

    if not can_delete:
        messages.error(request, '삭제 권한이 없습니다.')
        if redirect_url[1]:
            return redirect(redirect_url[0], pk=redirect_url[1])
        return redirect(redirect_url[0])

    comment.is_deleted = True
    comment.content = '삭제된 댓글입니다.'
    comment.save()

    _update_comment_count(
        coordinate=comment.coordinate,
        farming_journal=comment.farming_journal
    )

    messages.success(request, '댓글이 삭제되었습니다.')
    if redirect_url[1]:
        return redirect(redirect_url[0], pk=redirect_url[1])
    return redirect(redirect_url[0])


@require_POST
def comment_reply(request, pk):
    """대댓글 작성"""
    parent = get_object_or_404(Comment, pk=pk)
    coordinate = parent.coordinate
    content = request.POST.get('content', '').strip()
    photo = request.FILES.get('photo')

    if not content and not photo:
        messages.error(request, '댓글 내용이나 사진 중 하나는 입력해주세요.')
        return redirect('coordinates:detail', pk=coordinate.pk)

    photo_error = _validate_photo(photo)
    if photo_error:
        messages.error(request, photo_error)
        return redirect('coordinates:detail', pk=coordinate.pk)

    comment, actor_name, actor = _create_comment(
        request, content, photo=photo, parent=parent, coordinate=coordinate
    )
    if comment is None:
        messages.error(request, actor_name)
        return redirect('coordinates:detail', pk=coordinate.pk)

    # 알림 - 부모 댓글 작성자에게
    if parent.author and parent.author != actor:
        emoji = '📷' if photo else '💬'
        Notification.objects.create(
            recipient=parent.author,
            actor=actor,
            notification_type=Notification.NotificationType.COMMENT,
            coordinate=coordinate,
            message=f"{actor_name}님이 회원님의 댓글에 {emoji} 답글을 남겼어요"
        )

    _update_comment_count(coordinate=coordinate)

    messages.success(request, '답글이 등록되었습니다.')
    return redirect('coordinates:detail', pk=coordinate.pk)


# ===== 농사 일지 댓글 =====

@require_POST
def journal_comment_create(request, journal_id):
    """농사 일지 댓글 작성"""
    from apps.farming.models import FarmingJournal

    journal = get_object_or_404(FarmingJournal, pk=journal_id)
    content = request.POST.get('content', '').strip()

    if not content:
        messages.error(request, '댓글 내용을 입력해주세요.')
        return redirect('farming:journal_detail', pk=journal_id)

    comment, actor_name, actor = _create_comment(
        request, content, farming_journal=journal
    )
    if comment is None:
        messages.error(request, actor_name)
        return redirect('farming:journal_detail', pk=journal_id)

    _update_comment_count(farming_journal=journal)

    messages.success(request, '댓글이 등록되었습니다.')
    return redirect('farming:journal_detail', pk=journal_id)


@require_POST
def journal_comment_reply(request, pk):
    """농사 일지 대댓글 작성"""
    parent = get_object_or_404(Comment, pk=pk)
    journal = parent.farming_journal
    content = request.POST.get('content', '').strip()

    if not content:
        messages.error(request, '댓글 내용을 입력해주세요.')
        return redirect('farming:journal_detail', pk=journal.pk)

    comment, actor_name, actor = _create_comment(
        request, content, parent=parent, farming_journal=journal
    )
    if comment is None:
        messages.error(request, actor_name)
        return redirect('farming:journal_detail', pk=journal.pk)

    _update_comment_count(farming_journal=journal)

    messages.success(request, '답글이 등록되었습니다.')
    return redirect('farming:journal_detail', pk=journal.pk)
