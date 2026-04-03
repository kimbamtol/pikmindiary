"""Admin Panel views - 관리자 대시보드"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden

from apps.coordinates.models import Coordinate
from apps.reports.models import Report
from apps.accounts.models import CustomUser
from apps.rankings.utils import update_user_ranking


@staff_member_required
def dashboard(request):
    """관리자 대시보드"""
    pending_count = Coordinate.objects.filter(status=Coordinate.Status.PENDING).count()
    report_count = Report.objects.filter(status=Report.Status.PENDING).count()
    
    # 최근 대기 글
    recent_pending = Coordinate.objects.filter(
        status=Coordinate.Status.PENDING
    ).order_by('-created_at')[:5]
    
    # 최근 신고
    recent_reports = Report.objects.filter(
        status=Report.Status.PENDING
    ).order_by('-created_at')[:5]
    
    context = {
        'pending_count': pending_count,
        'report_count': report_count,
        'recent_pending': recent_pending,
        'recent_reports': recent_reports,
    }
    return render(request, 'admin_panel/dashboard.html', context)


@staff_member_required
def pending_list(request):
    """대기 글 목록"""
    queryset = Coordinate.objects.filter(
        status=Coordinate.Status.PENDING
    ).order_by('-created_at')
    
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'admin_panel/pending_list.html', context)


@staff_member_required
def approve_coordinate(request, pk):
    """좌표 승인"""
    coordinate = get_object_or_404(Coordinate, pk=pk)
    
    if request.method == 'POST':
        coordinate.status = Coordinate.Status.APPROVED
        coordinate.approved_at = timezone.now()
        coordinate.save()
        
        # 작성자 통계 및 랭킹 업데이트
        if coordinate.author:
            coordinate.author.total_posts = Coordinate.objects.filter(
                author=coordinate.author,
                status=Coordinate.Status.APPROVED
            ).count()
            coordinate.author.save(update_fields=['total_posts'])
            
            # 랭킹 업데이트
            update_user_ranking(coordinate.author)
        
        messages.success(request, f'"{coordinate.title}"이(가) 승인되었습니다.')
    
    return redirect('admin_panel:pending_list')


@staff_member_required
def reject_coordinate(request, pk):
    """좌표 거절"""
    coordinate = get_object_or_404(Coordinate, pk=pk)
    
    if request.method == 'POST':
        coordinate.status = Coordinate.Status.REJECTED
        coordinate.save()
        messages.success(request, f'"{coordinate.title}"이(가) 거절되었습니다.')
    
    return redirect('admin_panel:pending_list')


@staff_member_required
def report_list(request):
    """신고 목록"""
    status_filter = request.GET.get('status', 'PENDING')
    
    queryset = Report.objects.all()
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    queryset = queryset.order_by('-created_at')
    
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
    }
    return render(request, 'admin_panel/report_list.html', context)


@staff_member_required
def resolve_report(request, pk):
    """신고 처리"""
    report = get_object_or_404(Report, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        admin_note = request.POST.get('admin_note', '')
        
        report.admin_note = admin_note
        report.resolved_by = request.user
        report.resolved_at = timezone.now()
        
        if action == 'resolve':
            report.status = Report.Status.RESOLVED
            # 신고 대상 삭제 처리
            if report.coordinate:
                report.coordinate.status = Coordinate.Status.REJECTED
                report.coordinate.save()
            elif report.comment:
                report.comment.is_deleted = True
                report.comment.content = '삭제된 댓글입니다.'
                report.comment.save()
        else:
            report.status = Report.Status.DISMISSED
        
        report.save()
        messages.success(request, '신고가 처리되었습니다.')
    
    return redirect('admin_panel:report_list')


# ============================================
# 관리자 관리 (슈퍼유저 전용)
# ============================================

@staff_member_required
def user_list(request):
    """사용자 목록 (슈퍼유저 전용)"""
    # 슈퍼유저만 접근 가능
    if not request.user.is_superuser:
        messages.error(request, '이 페이지에 접근할 권한이 없습니다.')
        return redirect('admin_panel:dashboard')
    
    query = request.GET.get('q', '')
    queryset = CustomUser.objects.all().order_by('-date_joined')
    
    if query:
        queryset = queryset.filter(
            nickname__icontains=query
        ) | queryset.filter(
            email__icontains=query
        )
    
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'query': query,
    }
    return render(request, 'admin_panel/user_list.html', context)


@staff_member_required
def toggle_staff(request, pk):
    """관리자 권한 토글 (슈퍼유저 전용)"""
    # 슈퍼유저만 접근 가능
    if not request.user.is_superuser:
        messages.error(request, '이 작업을 수행할 권한이 없습니다.')
        return redirect('admin_panel:dashboard')
    
    user = get_object_or_404(CustomUser, pk=pk)
    
    # 자기 자신의 권한은 변경 불가
    if user == request.user:
        messages.error(request, '자신의 권한은 변경할 수 없습니다.')
        return redirect('admin_panel:user_list')
    
    # 다른 슈퍼유저의 권한은 변경 불가
    if user.is_superuser:
        messages.error(request, '슈퍼관리자의 권한은 변경할 수 없습니다.')
        return redirect('admin_panel:user_list')
    
    if request.method == 'POST':
        user.is_staff = not user.is_staff
        user.save()
        
        if user.is_staff:
            messages.success(request, f'{user.nickname}님을 관리자로 지정했습니다.')
        else:
            messages.success(request, f'{user.nickname}님의 관리자 권한을 해제했습니다.')
    
    return redirect('admin_panel:user_list')



# ============================================
# 게시글 일괄 관리 & 정지 관리 (슈퍼유저 전용)
# ============================================

from apps.accounts.models import UserBan

@staff_member_required
def batch_post_management(request):
    """게시글 일괄 관리 (슈퍼유저 전용)"""
    if not request.user.is_superuser:
        messages.error(request, '슈퍼관리자만 접근할 수 있습니다.')
        return redirect('admin_panel:dashboard')
    
    # 검색/필터
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    
    queryset = Coordinate.objects.all().order_by('-created_at')
    
    if query:
        queryset = queryset.filter(title__icontains=query)
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    paginator = Paginator(queryset, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'status_choices': Coordinate.Status.choices,
        'ban_durations': UserBan.BanDuration.choices,
    }
    return render(request, 'admin_panel/batch_post_management.html', context)


@staff_member_required
def batch_delete_posts(request):
    """게시글 일괄 삭제 (슈퍼유저 전용)"""
    if not request.user.is_superuser:
        messages.error(request, '슈퍼관리자만 접근할 수 있습니다.')
        return redirect('admin_panel:dashboard')
    
    if request.method == 'POST':
        post_ids = request.POST.getlist('post_ids')
        if post_ids:
            deleted_count = Coordinate.objects.filter(pk__in=post_ids).delete()[0]
            messages.success(request, f'{deleted_count}개의 게시글이 삭제되었습니다.')
        else:
            messages.warning(request, '선택된 게시글이 없습니다.')
    
    return redirect('admin_panel:batch_post_management')


@staff_member_required
def ban_user(request):
    """사용자/IP 정지 (슈퍼유저 전용)"""
    if not request.user.is_superuser:
        messages.error(request, '슈퍼관리자만 접근할 수 있습니다.')
        return redirect('admin_panel:dashboard')
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        ip_address = request.POST.get('ip_address')
        duration = request.POST.get('duration', '1d')
        reason = request.POST.get('reason', '')
        
        user = None
        if user_id:
            try:
                user = CustomUser.objects.get(pk=user_id)
            except CustomUser.DoesNotExist:
                pass
        
        # 정지 생성
        ban = UserBan(
            user=user,
            ip_address=ip_address if ip_address else None,
            duration=duration,
            reason=reason,
            banned_by=request.user
        )
        ban.save()
        
        target = user.nickname if user else ip_address
        messages.success(request, f'{target}이(가) {ban.get_duration_display()} 정지되었습니다.')
    
    return redirect('admin_panel:batch_post_management')


@staff_member_required
def ban_list(request):
    """정지 목록 (슈퍼유저 전용)"""
    if not request.user.is_superuser:
        messages.error(request, '슈퍼관리자만 접근할 수 있습니다.')
        return redirect('admin_panel:dashboard')
    
    show_active = request.GET.get('active', 'true') == 'true'
    
    queryset = UserBan.objects.all()
    if show_active:
        queryset = queryset.filter(is_active=True)
    
    queryset = queryset.order_by('-banned_at')
    
    paginator = Paginator(queryset, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'show_active': show_active,
    }
    return render(request, 'admin_panel/ban_list.html', context)


@staff_member_required
def unban_user(request, pk):
    """정지 해제 (슈퍼유저 전용)"""
    if not request.user.is_superuser:
        messages.error(request, '슈퍼관리자만 접근할 수 있습니다.')
        return redirect('admin_panel:dashboard')
    
    ban = get_object_or_404(UserBan, pk=pk)
    
    if request.method == 'POST':
        ban.is_active = False
        ban.unbanned_at = timezone.now()
        ban.unbanned_by = request.user
        ban.save()
        
        target = ban.user.nickname if ban.user else ban.ip_address
        messages.success(request, f'{target}의 정지가 해제되었습니다.')
    
    return redirect('admin_panel:ban_list')
