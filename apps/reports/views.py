"""Reports views - 신고"""
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import Report
from apps.coordinates.models import Coordinate
from apps.comments.models import Comment


@login_required
def report_coordinate(request, coordinate_id):
    """좌표 신고"""
    coordinate = get_object_or_404(Coordinate, pk=coordinate_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        detail = request.POST.get('detail', '')
        
        # 이미 신고했는지 확인
        if Report.objects.filter(reporter=request.user, coordinate=coordinate).exists():
            messages.warning(request, '이미 신고한 게시글입니다.')
            return redirect('coordinates:detail', pk=coordinate_id)
        
        Report.objects.create(
            reporter=request.user,
            coordinate=coordinate,
            reason=reason,
            detail=detail,
        )
        
        messages.success(request, '신고가 접수되었습니다.')
        return redirect('coordinates:detail', pk=coordinate_id)
    
    context = {
        'coordinate': coordinate,
        'reasons': Report.Reason.choices,
    }
    return render(request, 'reports/report_coordinate.html', context)


@login_required
def report_comment(request, comment_id):
    """댓글 신고"""
    comment = get_object_or_404(Comment, pk=comment_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        detail = request.POST.get('detail', '')
        
        # 이미 신고했는지 확인
        if Report.objects.filter(reporter=request.user, comment=comment).exists():
            messages.warning(request, '이미 신고한 댓글입니다.')
            return redirect('coordinates:detail', pk=comment.coordinate.pk)
        
        Report.objects.create(
            reporter=request.user,
            comment=comment,
            reason=reason,
            detail=detail,
        )
        
        messages.success(request, '신고가 접수되었습니다.')
        return redirect('coordinates:detail', pk=comment.coordinate.pk)
    
    context = {
        'comment': comment,
        'reasons': Report.Reason.choices,
    }
    return render(request, 'reports/report_comment.html', context)
