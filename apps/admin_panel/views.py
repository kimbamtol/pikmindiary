"""Admin Panel views - 관리자 대시보드"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.db import models

from apps.coordinates.models import Coordinate
from apps.reports.models import Report
from apps.accounts.models import CustomUser
from apps.rankings.utils import update_user_ranking


@staff_member_required
def dashboard(request):
    """관리자 대시보드"""
    pending_count = Coordinate.objects.filter(status=Coordinate.Status.PENDING).count()
    report_count = Report.objects.filter(status=Report.Status.PENDING).count()
    # 확인 완료 이후에 들어온 '사진이 달라요' 제보가 있는 글 수
    change_count = Coordinate.objects.filter(
        models.Q(change_checked_at__isnull=True)
        | models.Q(nerf_reports__created_at__gt=models.F('change_checked_at')),
        nerf_reports__isnull=False,
    ).distinct().count()
    
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
        'change_count': change_count,
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

            # 승인되면 그 글의 복사 수가 합계에 들어온다
            coordinate.author.recount_copy_total()

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
        # 거절되면 합계에서 빠진다
        if coordinate.author:
            coordinate.author.recount_copy_total()
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


# ===== 엽서 변경 제보 모아보기 =====

@staff_member_required
def change_list(request):
    """이용자들이 올린 '사진이 달라요' 제보를 글 단위로 모아 보여준다.

    신고 큐와 따로 둔다. 신고는 사람을 문제 삼는 창구이고 이쪽은 사실관계
    정정이라, 섞어두면 제보자가 신고 누르기를 망설인다 (건의 #28).
    """
    from apps.coordinates.models import NerfReport

    only = request.GET.get('only', '')

    reports = NerfReport.objects.select_related(
        'coordinate', 'coordinate__author'
    ).order_by('-created_at')

    buckets = {}
    for r in reports:
        coord = r.coordinate
        # 확인 완료 이후에 들어온 제보만 (운영자가 이미 본 건 다시 안 띄운다)
        if coord.change_checked_at and r.created_at <= coord.change_checked_at:
            continue
        b = buckets.get(coord.pk)
        if b is None:
            b = buckets[coord.pk] = {
                'coord': coord,
                'counts': {},
                'total': 0,
                'latest': r.created_at,
                'voters': [],
            }
        b['counts'][r.change_kind] = b['counts'].get(r.change_kind, 0) + 1
        b['total'] += 1
        b['latest'] = max(b['latest'], r.created_at)
        if len(b['voters']) < 6:
            b['voters'].append(r.user.nickname if r.user else '비회원')

    kind_labels = dict(NerfReport.ChangeKind.choices)
    rows = []
    for b in buckets.values():
        # 분류 정정 제보 중 표를 가장 많이 받은 것
        cat_votes = {
            k: n for k, n in b['counts'].items()
            if k in NerfReport.CATEGORY_FOR_KIND
        }
        suggested = None
        if cat_votes:
            top = max(cat_votes.items(), key=lambda kv: kv[1])[0]
            if NerfReport.CATEGORY_FOR_KIND[top] != b['coord'].category:
                suggested = {
                    'value': NerfReport.CATEGORY_FOR_KIND[top],
                    'label': dict(Coordinate.Category.choices)[
                        NerfReport.CATEGORY_FOR_KIND[top]
                    ],
                    'votes': cat_votes[top],
                }
        rows.append({
            **b,
            'breakdown': [
                (kind_labels[k], n) for k, n in sorted(
                    b['counts'].items(), key=lambda kv: -kv[1]
                )
            ],
            'suggested': suggested,
            'gone_votes': b['counts'].get(NerfReport.ChangeKind.GONE, 0),
            # 목록 카드의 「?」가 세는 것과 같은 값이다 (apps/coordinates/gone.py).
            # 없어졌다는 표와 그 반대표를 나란히 둬야 운영자가 판단할 수 있다.
            'gone_n': b['counts'].get(NerfReport.ChangeKind.GONE, 0),
            'alive_n': b['counts'].get(NerfReport.ChangeKind.ALIVE, 0),
            'first_image': b['coord'].images.first(),
        })

    if only == 'category':
        rows = [r for r in rows if r['suggested']]
    elif only == 'gone':
        rows = [r for r in rows if r['gone_votes']]

    rows.sort(key=lambda r: r['latest'], reverse=True)

    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin_panel/change_list.html', {
        'page_obj': page_obj,
        'total_rows': len(rows),
        'only': only,
        'categories': Coordinate.Category.choices,
    })


@staff_member_required
def change_sweep(request):
    """오래된 제보를 한 번에 '확인 완료'로 내린다.

    기능을 켠 날 기준으로 이미 몇 달 지난 제보가 104건 쌓여 있어서,
    목록을 처음 열면 옛날 것부터 다 뜬다. 그걸 손으로 하나씩 누르게 두면
    목록을 아예 안 보게 된다.
    """
    if request.method != 'POST':
        return redirect('admin_panel:change_list')

    try:
        days = int(request.POST.get('days', 30))
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 3650))

    cutoff = timezone.now() - timedelta(days=days)
    # 가장 최근 제보가 cutoff 보다 오래된 글만
    stale = Coordinate.objects.filter(
        nerf_reports__isnull=False
    ).annotate(
        last_report=models.Max('nerf_reports__created_at')
    ).filter(last_report__lt=cutoff).exclude(
        change_checked_at__gte=models.F('last_report')
    )
    ids = list(stale.values_list('pk', flat=True))
    Coordinate.objects.filter(pk__in=ids).update(change_checked_at=timezone.now())
    messages.success(request, f'{days}일 지난 제보 {len(ids)}건을 확인 완료로 내렸습니다.')
    return redirect(request.POST.get('next') or 'admin_panel:change_list')


@staff_member_required
def change_apply(request, pk):
    """제보 목록에서 누른 조치를 반영한다"""
    from apps.coordinates.models import NerfReport
    from apps.interactions.models import Notification

    if request.method != 'POST':
        return redirect('admin_panel:change_list')

    coordinate = get_object_or_404(Coordinate, pk=pk)
    action = request.POST.get('action', '')
    now = timezone.now()

    if action == 'category':
        new_category = request.POST.get('category', '')
        valid = dict(Coordinate.Category.choices)
        if new_category not in valid:
            messages.error(request, '분류 값이 잘못되었습니다.')
            return redirect(request.POST.get('next') or 'admin_panel:change_list')
        if new_category == coordinate.category:
            messages.info(request, '이미 그 분류입니다.')
            return redirect(request.POST.get('next') or 'admin_panel:change_list')

        old_label = coordinate.get_category_display()
        # [너프됨]은 '사진이 조금 바뀌었다'는 뜻으로 쓰이는 말이다.
        # 빅플 → 버섯처럼 엽서가 통째로 다른 것이 된 경우는 너프가 아니므로
        # 분류만 고치고 표시는 건드리지 않는다. 사진이 낡은 것도 맞지만
        # 그건 '사진이 달라요' 제보로 따로 들어온다.
        Coordinate.objects.filter(pk=pk).update(
            category=new_category,
            change_checked_at=now,
        )
        if coordinate.author:
            Notification.objects.create(
                recipient=coordinate.author,
                actor=request.user,
                notification_type=Notification.NotificationType.NERF,
                coordinate=coordinate,
                message=f"'{coordinate.title}'의 분류를 {old_label} → {valid[new_category]}(으)로 "
                        f"수정했어요. 제보를 확인한 결과입니다.",
            )
        messages.success(request, f'#{pk} 분류를 {old_label} → {valid[new_category]} 로 바꿨습니다.')

    elif action == 'nerf':
        Coordinate.objects.filter(pk=pk).update(
            is_nerfed=True,
            nerfed_at=coordinate.nerfed_at or now,
            change_checked_at=now,
        )
        messages.success(request, f'#{pk} [너프됨] 표시를 켰습니다.')

    elif action == 'gone':
        # 그 자리에 아무것도 없다고 확정한다. [너프됨](사진이 조금 달라짐)과는
        # 다른 이야기라 같이 켜지 않는다. 글은 지우지 않고 목록에 흐리게 남긴다 -
        # 그래야 「어 살아났는데요」 하는 제보를 다시 받을 수 있다.
        Coordinate.objects.filter(pk=pk).update(
            is_gone=True,
            gone_at=coordinate.gone_at or now,
            change_checked_at=now,
        )
        if coordinate.author:
            Notification.objects.create(
                recipient=coordinate.author,
                actor=request.user,
                notification_type=Notification.NotificationType.NERF,
                coordinate=coordinate,
                message=f"'{coordinate.title}'이(가) 없어졌다는 제보를 확인했어요. "
                        f"목록에서 흐리게 표시됩니다. 다시 생겼다면 알려주세요.",
            )
        messages.success(request, f'#{pk} 「없어짐」으로 확정했습니다.')

    elif action == 'alive':
        # 가봤더니 멀쩡하더라. 확정을 되돌리고 「없어졌다」 표만 지운다.
        # 「사진이 달라요」 같은 다른 제보는 건드리지 않는다.
        NerfReport.objects.filter(
            coordinate=coordinate,
            change_kind__in=(NerfReport.ChangeKind.GONE, NerfReport.ChangeKind.ALIVE),
        ).delete()
        Coordinate.objects.filter(pk=pk).update(
            is_gone=False, gone_at=None, change_checked_at=now,
        )
        messages.success(request, f'#{pk} 「없어짐」을 풀고 그 제보를 지웠습니다.')

    elif action == 'clear':
        NerfReport.objects.filter(coordinate=coordinate).delete()
        Coordinate.objects.filter(pk=pk).update(
            nerf_report_count=0, is_nerfed=False, nerfed_at=None,
            is_gone=False, gone_at=None, change_checked_at=now,
        )
        messages.success(request, f'#{pk} 제보를 지우고 표시를 껐습니다.')

    elif action == 'done':
        Coordinate.objects.filter(pk=pk).update(change_checked_at=now)
        messages.success(request, f'#{pk} 확인 완료로 넘겼습니다.')

    else:
        messages.error(request, '알 수 없는 조치입니다.')

    return redirect(request.POST.get('next') or 'admin_panel:change_list')
