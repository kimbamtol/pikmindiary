"""Rankings views - 랭킹"""
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta

from .models import Ranking
from .utils import get_period_start


def ranking_list(request):
    """전체 랭킹"""
    period_type = request.GET.get('period', 'ALL')
    
    if period_type == 'WEEKLY':
        return weekly_ranking(request)
    elif period_type == 'MONTHLY':
        return monthly_ranking(request)
    
    # 전체 랭킹 - utils의 get_period_start 사용
    period_start = get_period_start(Ranking.PeriodType.ALL)
    rankings = Ranking.objects.filter(
        period_type=Ranking.PeriodType.ALL,
        period_start=period_start,
        approved_posts_count__gt=0
    ).select_related('user').order_by('rank')[:100]
    
    context = {
        'rankings': rankings,
        'period_type': 'ALL',
        'period_label': '전체',
    }
    return render(request, 'rankings/list.html', context)


def weekly_ranking(request):
    """주간 랭킹"""
    today = timezone.now().date()
    # 이번 주 월요일
    week_start = today - timedelta(days=today.weekday())
    
    rankings = Ranking.objects.filter(
        period_type=Ranking.PeriodType.WEEKLY,
        period_start=week_start,
        approved_posts_count__gt=0
    ).select_related('user').order_by('rank')[:100]
    
    context = {
        'rankings': rankings,
        'period_type': 'WEEKLY',
        'period_label': f'주간 ({week_start.strftime("%m/%d")} ~ )',
    }
    return render(request, 'rankings/list.html', context)


def monthly_ranking(request):
    """월간 랭킹"""
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    rankings = Ranking.objects.filter(
        period_type=Ranking.PeriodType.MONTHLY,
        period_start=month_start,
        approved_posts_count__gt=0
    ).select_related('user').order_by('rank')[:100]
    
    context = {
        'rankings': rankings,
        'period_type': 'MONTHLY',
        'period_label': f'월간 ({month_start.strftime("%Y년 %m월")})',
    }
    return render(request, 'rankings/list.html', context)
