"""Comments views - 댓글"""
import logging

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils.translation import gettext as _
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone

from .models import Comment
from apps.coordinates.models import Coordinate
from apps.interactions.models import Notification, CommentLike


# ===== 헬퍼 함수 =====

def _validate_photo(photo):
    """사진 검사 + 손질. (쓸 파일, 오류메시지, 원본) 을 돌려준다.

    예전에는 content_type 만 봤는데 그건 브라우저가 적어 보내는 값이라
    아이폰 HEIC 가 application/octet-stream 으로 와서 막혔다.
    이제 공용 모듈이 PIL 로 직접 열어보고, HEIC 는 JPEG 로 바꾸고
    눕힌 사진은 세워서 돌려준다.

    좌표 글과 같은 규격을 쓴다 — 1280px, 품질 82, 비치지 않는 PNG 는 JPEG.
    카톡 스크린샷이 PNG 로 올라와서 댓글 사진 평균이 882KB 였다.
    """
    from django.conf import settings as dj_settings

    from apps.core.images import prepare_upload, stash_original

    origin = stash_original(photo)
    ready, err = prepare_upload(
        photo, max_px=dj_settings.IMAGE_MAX_PX, prefer_jpeg=True
    )
    return ready, err, origin


def _attach_photo(comment, photo, origin=None):
    """사진을 '작성시각_댓글번호' 이름으로 붙이고 원본은 media 바깥에 보관한다.

    댓글을 먼저 만들고 사진을 나중에 붙이는 이유는 번호(pk)가 필요해서다.
    여기서 터져도 댓글 본문은 이미 남아 있다 — 사진만 빠진다.
    """
    from apps.core.images import archive_original, name_as, stem_of

    made = timezone.localtime(comment.created_at)
    stem = '%s_%s' % (made.strftime('%Y_%m_%d_%H_%M_%S'), comment.pk)
    comment.photo = name_as(photo, stem)
    comment.save(update_fields=['photo'])

    raw, orig_name = origin or (None, '')
    if raw:
        archive_original(raw, orig_name, 'comments', stem_of(comment.photo.name))


def _create_comment(request, content, photo=None, parent=None, coordinate=None,
                    farming_journal=None, brag_post=None, origin=None):
    """회원/비회원 댓글 생성 공통 로직. (comment, actor_name, actor) 튜플 반환. 실패 시 (None, error_msg, None)"""
    kwargs = {
        'content': content,
        'parent': parent,
        'coordinate': coordinate,
        'farming_journal': farming_journal,
        'brag_post': brag_post,
    }

    if request.user.is_authenticated:
        kwargs['author'] = request.user
        comment = Comment.objects.create(**kwargs)
        actor_name, actor = request.user.nickname, request.user
    else:
        guest_nickname = request.POST.get('guest_nickname', '익명')
        guest_password = request.POST.get('guest_password', '')
        if not guest_password:
            return None, _('비회원은 비밀번호를 입력해야 합니다.'), None
        kwargs['guest_nickname'] = guest_nickname
        kwargs['guest_password'] = make_password(guest_password)
        comment = Comment.objects.create(**kwargs)
        actor_name, actor = guest_nickname, None

    if photo:
        try:
            _attach_photo(comment, photo, origin)
        except Exception as e:
            logging.getLogger(__name__).warning(
                '댓글 사진 붙이기 실패 (댓글은 저장됨) pk=%s: %s', comment.pk, e)

    return comment, actor_name, actor


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
        messages.error(request, _('댓글 내용이나 사진 중 하나는 입력해주세요.'))
        return redirect('coordinates:detail', pk=coordinate_id)

    photo, photo_error, photo_origin = _validate_photo(photo)
    if photo_error:
        messages.error(request, photo_error)
        return redirect('coordinates:detail', pk=coordinate_id)

    comment, actor_name, actor = _create_comment(
        request, content, photo=photo, coordinate=coordinate, origin=photo_origin
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
            message=_("%(name)s님이 '%(title)s'에 %(emoji)s 댓글을 남겼어요") % {'name': actor_name, 'title': coordinate.title, 'emoji': emoji}
        )

    _update_comment_count(coordinate=coordinate)

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.headers.get('HX-Request') or is_ajax:
        return JsonResponse({'success': True, 'comment_count': coordinate.comment_count})

    messages.success(request, _('댓글이 등록되었습니다.'))
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
        messages.error(request, _('수정 권한이 없습니다.'))
        return redirect('coordinates:detail', pk=coordinate_id)

    content = request.POST.get('content', '').strip()
    if content:
        comment.content = content
        comment.save()
        messages.success(request, _('댓글이 수정되었습니다.'))

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
        messages.error(request, _('삭제 권한이 없습니다.'))
        if redirect_url[1]:
            return redirect(redirect_url[0], pk=redirect_url[1])
        return redirect(redirect_url[0])

    comment.is_deleted = True
    comment.content = _('삭제된 댓글입니다.')
    comment.save()

    _update_comment_count(
        coordinate=comment.coordinate,
        farming_journal=comment.farming_journal
    )

    messages.success(request, _('댓글이 삭제되었습니다.'))
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
        messages.error(request, _('댓글 내용이나 사진 중 하나는 입력해주세요.'))
        return redirect('coordinates:detail', pk=coordinate.pk)

    photo, photo_error, photo_origin = _validate_photo(photo)
    if photo_error:
        messages.error(request, photo_error)
        return redirect('coordinates:detail', pk=coordinate.pk)

    comment, actor_name, actor = _create_comment(
        request, content, photo=photo, parent=parent, coordinate=coordinate,
        origin=photo_origin
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
            message=_("%(name)s님이 회원님의 댓글에 %(emoji)s 답글을 남겼어요") % {'name': actor_name, 'emoji': emoji}
        )

    _update_comment_count(coordinate=coordinate)

    messages.success(request, _('답글이 등록되었습니다.'))
    return redirect('coordinates:detail', pk=coordinate.pk)


@require_GET
def comment_list(request, coordinate_id):
    """카드 댓글 모달용 댓글 목록"""
    coordinate = get_object_or_404(Coordinate, pk=coordinate_id)
    comments = Comment.objects.filter(
        coordinate=coordinate, is_deleted=False, parent__isnull=True
    ).select_related('author').prefetch_related(
        'replies', 'replies__author'
    ).order_by('-created_at')

    # 좋아요 상태
    user_liked_comments = set()
    if request.user.is_authenticated:
        user_liked_comments = set(
            CommentLike.objects.filter(
                user=request.user,
                comment__coordinate=coordinate
            ).values_list('comment_id', flat=True)
        )
    else:
        user_liked_comments = set(request.session.get('liked_comments', []))

    return render(request, 'comments/_comment_modal_content.html', {
        'comments': comments,
        'coordinate': coordinate,
        'user_liked_comments': user_liked_comments,
    })


# ===== 농사 일지 댓글 =====

@require_POST
def journal_comment_create(request, journal_id):
    """농사 일지 댓글 작성"""
    from apps.farming.models import FarmingJournal

    journal = get_object_or_404(FarmingJournal, pk=journal_id)
    content = request.POST.get('content', '').strip()

    if not content:
        messages.error(request, _('댓글 내용을 입력해주세요.'))
        return redirect('farming:journal_detail', pk=journal_id)

    comment, actor_name, actor = _create_comment(
        request, content, farming_journal=journal
    )
    if comment is None:
        messages.error(request, actor_name)
        return redirect('farming:journal_detail', pk=journal_id)

    _update_comment_count(farming_journal=journal)

    messages.success(request, _('댓글이 등록되었습니다.'))
    return redirect('farming:journal_detail', pk=journal_id)


@require_POST
def journal_comment_reply(request, pk):
    """농사 일지 대댓글 작성"""
    parent = get_object_or_404(Comment, pk=pk)
    journal = parent.farming_journal
    content = request.POST.get('content', '').strip()

    if not content:
        messages.error(request, _('댓글 내용을 입력해주세요.'))
        return redirect('farming:journal_detail', pk=journal.pk)

    comment, actor_name, actor = _create_comment(
        request, content, parent=parent, farming_journal=journal
    )
    if comment is None:
        messages.error(request, actor_name)
        return redirect('farming:journal_detail', pk=journal.pk)

    _update_comment_count(farming_journal=journal)

    messages.success(request, _('답글이 등록되었습니다.'))
    return redirect('farming:journal_detail', pk=journal.pk)
