"""랭킹 유틸리티 함수"""
from django.utils import timezone
from datetime import timedelta, datetime
from .models import Ranking


def get_period_start(period_type):
    """기간 시작일 계산"""
    today = timezone.now().date()
    
    if period_type == Ranking.PeriodType.WEEKLY:
        # 이번 주 월요일
        return today - timedelta(days=today.weekday())
    elif period_type == Ranking.PeriodType.MONTHLY:
        # 이번 달 1일
        return today.replace(day=1)
    else:  # ALL
        # 전체 기간은 서비스 시작일 기준 (2024-01-01 고정)
        # 이 날짜는 변경하지 않음 - 전체 누적 랭킹용
        return datetime(2024, 1, 1).date()


def update_user_ranking(user):
    """사용자 랭킹 업데이트 (기간당 2개 쿼리로 최적화)"""
    from apps.coordinates.models import Coordinate
    from apps.interactions.models import Like, ValidityFeedback
    from apps.farming.models import FarmingJournalLike
    from django.db.models import Sum, Count, Q

    if not user:
        return

    for period_type in [Ranking.PeriodType.ALL, Ranking.PeriodType.WEEKLY, Ranking.PeriodType.MONTHLY]:
        period_start = get_period_start(period_type)

        ranking, created = Ranking.objects.get_or_create(
            user=user,
            period_type=period_type,
            period_start=period_start,
        )

        is_all = period_type == Ranking.PeriodType.ALL

        if is_all:
            coord_qs = Coordinate.objects.filter(author=user, status=Coordinate.Status.APPROVED)
            like_qs = Like.objects.filter(coordinate__author=user)
            validity_qs = ValidityFeedback.objects.filter(coordinate__author=user)
            farming_qs = FarmingJournalLike.objects.filter(journal__author=user)
        else:
            start_datetime = timezone.make_aware(datetime.combine(period_start, datetime.min.time()))
            coord_qs = Coordinate.objects.filter(author=user, status=Coordinate.Status.APPROVED, approved_at__gte=start_datetime)
            like_qs = Like.objects.filter(coordinate__author=user, created_at__gte=start_datetime)
            validity_qs = ValidityFeedback.objects.filter(coordinate__author=user, created_at__gte=start_datetime)
            farming_qs = FarmingJournalLike.objects.filter(journal__author=user, created_at__gte=start_datetime)

        # 좌표 통계: 승인된 글 수 + 복사 합계 (1개 쿼리)
        coord_stats = coord_qs.aggregate(
            posts=Count('id'),
            copies=Sum('copy_count')
        )
        ranking.approved_posts_count = coord_stats['posts'] or 0
        ranking.copy_received_count = coord_stats['copies'] or 0

        # 좋아요 수 (1개 쿼리)
        ranking.likes_received_count = like_qs.count()

        # VALID/INVALID 동시 집계 (1개 쿼리)
        validity_stats = validity_qs.aggregate(
            valid=Count('id', filter=Q(feedback_type=ValidityFeedback.FeedbackType.VALID)),
            invalid=Count('id', filter=Q(feedback_type=ValidityFeedback.FeedbackType.INVALID)),
        )
        ranking.valid_received_count = validity_stats['valid'] or 0
        ranking.invalid_received_count = validity_stats['invalid'] or 0

        # 농사 일지 좋아요 수 (1개 쿼리)
        ranking.farming_likes_received_count = farming_qs.count()

        ranking.calculate_score()
        ranking.save(update_fields=[
            'approved_posts_count',
            'likes_received_count',
            'valid_received_count',
            'invalid_received_count',
            'farming_likes_received_count',
            'copy_received_count',
            'score',
            'updated_at'
        ])
    
    # 순위 재계산
    recalculate_ranks()


def recalculate_ranks():
    """전체 순위 재계산"""
    for period_type in [Ranking.PeriodType.ALL, Ranking.PeriodType.WEEKLY, Ranking.PeriodType.MONTHLY]:
        period_start = get_period_start(period_type)
        
        rankings = Ranking.objects.filter(
            period_type=period_type,
            period_start=period_start
        ).order_by('-score')
        
        for idx, ranking in enumerate(rankings, start=1):
            if ranking.rank != idx:
                ranking.rank = idx
                ranking.save(update_fields=['rank'])
