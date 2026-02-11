"""Interactions views - 좋아요, 북마크, 유효성 평가"""
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Like, Bookmark, ValidityFeedback, Notification, CommentLike
from apps.coordinates.models import Coordinate
from apps.comments.models import Comment


@require_POST
def toggle_like(request, coordinate_id):
    """좋아요 토글 (비회원도 가능, 본인 글 제외)"""
    coordinate = get_object_or_404(Coordinate, pk=coordinate_id)
    
    # 본인 글은 좋아요 불가
    if request.user.is_authenticated and coordinate.author == request.user:
        return JsonResponse({'error': '본인 글에는 좋아요를 누를 수 없습니다.'}, status=400)
    
    if request.user.is_authenticated:
        # 로그인 사용자: DB에서 관리
        like, created = Like.objects.get_or_create(
            user=request.user,
            coordinate=coordinate
        )
        
        if not created:
            like.delete()
            coordinate.like_count = max(0, coordinate.like_count - 1)
            liked = False
        else:
            coordinate.like_count += 1
            liked = True
            
            # 알림 생성 (작성자가 있고, 본인이 아닐 때)
            if coordinate.author and coordinate.author != request.user:
                Notification.objects.create(
                    recipient=coordinate.author,
                    actor=request.user,
                    notification_type=Notification.NotificationType.LIKE,
                    coordinate=coordinate,
                    message=f"{request.user.nickname}님이 '{coordinate.title}'에 ❤️ 좋아요를 눌렀어요"
                )
    else:
        # 비회원: 세션으로 관리
        liked_coords = request.session.get('liked_coords', [])
        
        if coordinate_id in liked_coords:
            liked_coords.remove(coordinate_id)
            coordinate.like_count = max(0, coordinate.like_count - 1)
            liked = False
        else:
            liked_coords.append(coordinate_id)
            coordinate.like_count += 1
            liked = True
            
            # 비회원 좋아요 알림 (작성자가 있을 때)
            if coordinate.author:
                Notification.objects.create(
                    recipient=coordinate.author,
                    actor=None,
                    notification_type=Notification.NotificationType.LIKE,
                    coordinate=coordinate,
                    message=f"익명님이 '{coordinate.title}'에 ❤️ 좋아요를 눌렀어요"
                )
        
        request.session['liked_coords'] = liked_coords
    
    coordinate.save(update_fields=['like_count'])
    
    # 작성자 통계 및 랭킹 업데이트
    if coordinate.author:
        coordinate.author.total_likes_received = Like.objects.filter(
            coordinate__author=coordinate.author
        ).count()
        coordinate.author.save(update_fields=['total_likes_received'])
        
        # 랭킹 동기화
        from apps.rankings.utils import update_user_ranking
        update_user_ranking(coordinate.author)
    
    return JsonResponse({
        'liked': liked,
        'like_count': coordinate.like_count,
    })


@require_POST
def toggle_comment_like(request, comment_id):
    """댓글 좋아요 토글 (비회원도 가능, 본인 댓글 제외)"""
    comment = get_object_or_404(Comment, pk=comment_id)

    # 본인 댓글은 좋아요 불가
    if request.user.is_authenticated and comment.author == request.user:
        return JsonResponse({'error': '본인 댓글에는 좋아요를 누를 수 없습니다.'}, status=400)

    if request.user.is_authenticated:
        # 로그인 사용자: DB에서 관리
        like, created = CommentLike.objects.get_or_create(
            user=request.user,
            comment=comment
        )

        if not created:
            like.delete()
            liked = False
        else:
            liked = True
    else:
        # 비회원: 세션으로 관리
        liked_comments = request.session.get('liked_comments', [])

        if comment_id in liked_comments:
            liked_comments.remove(comment_id)
            liked = False
        else:
            liked_comments.append(comment_id)
            liked = True

        request.session['liked_comments'] = liked_comments

    return JsonResponse({
        'liked': liked,
        'like_count': comment.like_count,
    })


@login_required
@require_POST
def toggle_bookmark(request, coordinate_id):
    """북마크 토글 (로그인 필수 - 마이페이지 기능)"""
    coordinate = get_object_or_404(Coordinate, pk=coordinate_id)
    
    bookmark, created = Bookmark.objects.get_or_create(
        user=request.user,
        coordinate=coordinate
    )
    
    if not created:
        bookmark.delete()
        coordinate.bookmark_count = max(0, coordinate.bookmark_count - 1)
        bookmarked = False
    else:
        coordinate.bookmark_count += 1
        bookmarked = True
    
    coordinate.save(update_fields=['bookmark_count'])
    
    return JsonResponse({
        'bookmarked': bookmarked,
        'bookmark_count': coordinate.bookmark_count,
    })


@require_POST
def submit_validity(request, coordinate_id):
    """유효성 평가 제출 (비회원도 가능, 본인 글 제외, 작성 1개월 후부터)"""
    from datetime import timedelta
    
    coordinate = get_object_or_404(Coordinate, pk=coordinate_id)
    feedback_type = request.POST.get('feedback_type')
    
    # 작성 1개월 경과 체크
    one_month_ago = timezone.now() - timedelta(days=30)
    if coordinate.created_at > one_month_ago:
        return JsonResponse({'error': '작성 후 1개월이 지난 게시글만 평가할 수 있습니다.'}, status=400)
    
    # 본인 글은 평가 불가
    if request.user.is_authenticated and coordinate.author == request.user:
        return JsonResponse({'error': '본인 글은 평가할 수 없습니다.'}, status=400)
    
    if feedback_type not in ['VALID', 'INVALID']:
        return JsonResponse({'error': '잘못된 평가 유형입니다.'}, status=400)
    
    if request.user.is_authenticated:
        # 로그인 사용자: DB에서 관리
        existing = ValidityFeedback.objects.filter(
            user=request.user,
            coordinate=coordinate
        ).first()
        
        if existing:
            old_type = existing.feedback_type
            
            if old_type == feedback_type:
                # 같은 평가 클릭 시 취소
                existing.delete()
                if old_type == 'VALID':
                    coordinate.valid_count = max(0, coordinate.valid_count - 1)
                else:
                    coordinate.invalid_count = max(0, coordinate.invalid_count - 1)
                submitted = None
            else:
                # 다른 평가로 변경
                existing.feedback_type = feedback_type
                existing.save()
                
                if feedback_type == 'VALID':
                    coordinate.valid_count += 1
                    coordinate.invalid_count = max(0, coordinate.invalid_count - 1)
                else:
                    coordinate.invalid_count += 1
                    coordinate.valid_count = max(0, coordinate.valid_count - 1)
                submitted = feedback_type
        else:
            # 새 평가
            ValidityFeedback.objects.create(
                user=request.user,
                coordinate=coordinate,
                feedback_type=feedback_type
            )
            
            if feedback_type == 'VALID':
                coordinate.valid_count += 1
            else:
                coordinate.invalid_count += 1
            submitted = feedback_type
    else:
        # 비회원: 세션으로 관리
        validity_coords = request.session.get('validity_coords', {})
        coord_key = str(coordinate_id)
        current_vote = validity_coords.get(coord_key)
        
        if current_vote == feedback_type:
            # 같은 평가 클릭 시 취소
            del validity_coords[coord_key]
            if feedback_type == 'VALID':
                coordinate.valid_count = max(0, coordinate.valid_count - 1)
            else:
                coordinate.invalid_count = max(0, coordinate.invalid_count - 1)
            submitted = None
        else:
            if current_vote:
                # 기존 투표 취소
                if current_vote == 'VALID':
                    coordinate.valid_count = max(0, coordinate.valid_count - 1)
                else:
                    coordinate.invalid_count = max(0, coordinate.invalid_count - 1)
            
            # 새 투표
            validity_coords[coord_key] = feedback_type
            if feedback_type == 'VALID':
                coordinate.valid_count += 1
            else:
                coordinate.invalid_count += 1
            submitted = feedback_type
        
        request.session['validity_coords'] = validity_coords
    
    coordinate.last_verified_at = timezone.now()
    coordinate.save(update_fields=['valid_count', 'invalid_count', 'last_verified_at'])
    
    # 작성자 통계 및 랭킹 업데이트
    if coordinate.author:
        coordinate.author.total_valid_received = ValidityFeedback.objects.filter(
            coordinate__author=coordinate.author,
            feedback_type='VALID'
        ).count()
        coordinate.author.save(update_fields=['total_valid_received'])
        
        # 랭킹 동기화
        from apps.rankings.utils import update_user_ranking
        update_user_ranking(coordinate.author)
    
    return JsonResponse({
        'submitted': submitted,
        'valid_count': coordinate.valid_count,
        'invalid_count': coordinate.invalid_count,
    })


# ===== 알림 API =====

from django.contrib.auth.decorators import login_required

@login_required
def get_notifications(request):
    """알림 목록 조회 (최근 20개)"""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related('actor', 'coordinate')[:20]
    
    data = []
    for notif in notifications:
        data.append({
            'id': notif.id,
            'type': notif.notification_type,
            'message': notif.message,
            'coordinate_id': notif.coordinate.pk if notif.coordinate else None,
            'coordinate_title': notif.coordinate.title if notif.coordinate else None,
            'actor_nickname': notif.actor.nickname if notif.actor else None,
            'is_read': notif.is_read,
            'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    
    return JsonResponse({'notifications': data})


@login_required
def get_unread_count(request):
    """읽지 않은 알림 개수"""
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    return JsonResponse({'unread_count': count})


@login_required
@require_POST
def mark_notification_read(request, pk):
    """알림 읽음 처리"""
    try:
        notification = Notification.objects.get(pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'error': '알림을 찾을 수 없습니다.'}, status=404)


@login_required
@require_POST
def mark_all_notifications_read(request):
    """모든 알림 읽음 처리"""
    Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(is_read=True)
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def delete_all_notifications(request):
    """모든 알림 삭제"""
    Notification.objects.filter(recipient=request.user).delete()
    
    return JsonResponse({'success': True})
