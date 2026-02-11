"""Coordinates views - 좌표 게시글 CRUD"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.contrib.auth.hashers import make_password, check_password

from .models import Coordinate, CoordinateImage
from apps.interactions.models import Like, Bookmark
from apps.rankings.utils import update_user_ranking


def coordinate_list(request):
    """좌표 목록 (검색/필터/정렬) - 무한 스크롤 지원"""
    queryset = Coordinate.objects.filter(status=Coordinate.Status.APPROVED)
    
    # 검색
    query = request.GET.get('q', '')
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query) |
            Q(postcard_name__icontains=query) |
            Q(description__icontains=query) |
            Q(author__nickname__icontains=query)
        )
    
    # 카테고리 필터
    category = request.GET.get('category', '')
    if category:
        queryset = queryset.filter(category=category)
    
    # 지역 필터
    region_filter = request.GET.get('region', '')
    if region_filter:
        queryset = queryset.filter(region=region_filter)
    
    # 정렬
    sort = request.GET.get('sort', 'latest')
    if sort == 'likes':
        queryset = queryset.order_by('-like_count', '-created_at')
    elif sort == 'copies':
        queryset = queryset.order_by('-copy_count', '-created_at')
    elif sort == 'bookmarks':
        queryset = queryset.order_by('-bookmark_count', '-created_at')
    else:  # latest
        queryset = queryset.order_by('-created_at')
    
    # 무한 스크롤을 위한 페이지네이션 (12개씩)
    PAGE_SIZE = 12
    page_number = request.GET.get('page', '1')
    try:
        page_number = int(page_number)
    except ValueError:
        page_number = 1

    offset = (page_number - 1) * PAGE_SIZE
    first_page_items = list(queryset[offset:offset + PAGE_SIZE])
    has_next = queryset.count() > offset + PAGE_SIZE
    
    # AJAX 요청인 경우 JSON으로 카드 HTML 반환
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.template.loader import render_to_string
        cards_html = render_to_string('coordinates/_card_list.html', {
            'coords': first_page_items,
        }, request=request)
        return JsonResponse({
            'html': cards_html,
            'has_next': has_next,
            'next_page': page_number + 1 if has_next else None,
        })
    
    # TOP 5 랭커 데이터 (카테고리별 글 수 포함)
    from apps.rankings.models import Ranking
    from django.db.models import Count, Q as DQ
    from datetime import date
    
    top_rankings = Ranking.objects.filter(
        period_type='ALL',
        rank__gt=0,
        rank__lte=5,
        approved_posts_count__gt=0
    ).select_related('user').order_by('rank')[:5]
    
    # 각 랭커의 카테고리별 글 수 계산 (1개 쿼리로 배치 처리)
    ranker_user_ids = [r.user_id for r in top_rankings]
    category_counts_qs = Coordinate.objects.filter(
        author_id__in=ranker_user_ids,
        status=Coordinate.Status.APPROVED
    ).values('author_id', 'category').annotate(count=Count('id'))

    # {user_id: {'MUSHROOM': n, ...}} 형태로 매핑
    user_category_map = {}
    for row in category_counts_qs:
        uid = row['author_id']
        if uid not in user_category_map:
            user_category_map[uid] = {}
        user_category_map[uid][row['category']] = row['count']

    ranker_stats = []
    for ranking in top_rankings:
        cats = user_category_map.get(ranking.user_id, {})
        stats = {
            'ranking': ranking,
            'mushroom': cats.get('MUSHROOM', 0),
            'bigflower': cats.get('BIGFLOWER', 0),
            'seedling': cats.get('SEEDLING', 0),
            'total_posts': sum(cats.values()),
        }
        ranker_stats.append(stats)
    
    # 사이트 공지 (감사 메시지 등)
    from apps.core.models import SiteNotice
    try:
        site_notice = SiteNotice.objects.get(location='coordinates_list', is_active=True)
    except SiteNotice.DoesNotExist:
        site_notice = None
    
    context = {
        'coords': first_page_items,
        'query': query,
        'category': category,
        'region_filter': region_filter,
        'sort': sort,
        'categories': Coordinate.Category.choices,
        'regions': Coordinate.Region.choices,
        'ranker_stats': ranker_stats,
        'has_next': has_next,
        'site_notice': site_notice,
    }
    return render(request, 'coordinates/list.html', context)


def coordinate_detail(request, pk):
    """좌표 상세"""
    from datetime import timedelta
    
    coordinate = get_object_or_404(Coordinate, pk=pk)
    
    # 미승인 글은 작성자 또는 관리자만 볼 수 있음
    if coordinate.status != Coordinate.Status.APPROVED:
        if not request.user.is_authenticated:
            messages.error(request, _('접근 권한이 없습니다.'))
            return redirect('coordinates:list')
        if coordinate.author != request.user and not request.user.is_staff:
            messages.error(request, _('접근 권한이 없습니다.'))
            return redirect('coordinates:list')
    
    # 조회수 증가
    coordinate.view_count += 1
    coordinate.save(update_fields=['view_count'])
    
    # 사용자 상호작용 상태
    user_liked = False
    user_bookmarked = False
    if request.user.is_authenticated:
        user_liked = Like.objects.filter(user=request.user, coordinate=coordinate).exists()
        user_bookmarked = Bookmark.objects.filter(user=request.user, coordinate=coordinate).exists()

    # 댓글 정렬
    from apps.comments.models import Comment
    from apps.interactions.models import CommentLike
    from django.db.models import Count

    sort = request.GET.get('sort', 'likes')  # 기본값: 좋아요순

    comments = Comment.objects.filter(
        coordinate=coordinate,
        is_deleted=False,
        parent__isnull=True  # 최상위 댓글만
    ).select_related('author').prefetch_related('replies')

    # 정렬 적용
    if sort == 'newest':
        comments = comments.order_by('-created_at')
    elif sort == 'oldest':
        comments = comments.order_by('created_at')
    else:  # likes (기본)
        # 좋아요 수로 정렬 (많은 순)
        comments = comments.annotate(
            total_likes=Count('likes')
        ).order_by('-total_likes', '-created_at')

    # 사용자가 좋아요한 댓글 ID 목록
    user_liked_comments = []
    if request.user.is_authenticated:
        user_liked_comments = list(
            CommentLike.objects.filter(
                user=request.user,
                comment__coordinate=coordinate
            ).values_list('comment_id', flat=True)
        )
    else:
        # 비회원은 세션에서 가져오기
        user_liked_comments = request.session.get('liked_comments', [])

    context = {
        'coordinate': coordinate,
        'images': coordinate.images.all(),
        'user_liked': user_liked,
        'user_bookmarked': user_bookmarked,
        'comments': comments,
        'comment_sort': sort,
        'user_liked_comments': user_liked_comments,
    }
    return render(request, 'coordinates/detail.html', context)


def coordinate_create(request):
    """좌표 작성"""
    from datetime import datetime, time as dt_time
    
    # 클라이언트 IP 가져오기
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    if request.method == 'POST':
        title = request.POST.get('title')
        postcard_name = request.POST.get('postcard_name', '')
        description = request.POST.get('description', '')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        category = request.POST.get('category', Coordinate.Category.OTHER)
        
        # 비회원 처리
        guest_nickname = request.POST.get('guest_nickname', '')
        guest_password = request.POST.get('guest_password', '')
        
        if request.user.is_authenticated:
            author = request.user
            hashed_password = ''
        else:
            # 비회원 - 닉네임과 비밀번호 필수
            if not guest_nickname or not guest_password:
                messages.error(request, _('비회원은 닉네임과 비밀번호를 입력해야 합니다.'))
                return render(request, 'coordinates/create.html', {
                    'categories': Coordinate.Category.choices,
                })
            author = None
            hashed_password = make_password(guest_password)
        
        # ===== 일일 업로드 제한 체크 =====
        from apps.core.models import SiteSettings
        from apps.rankings.models import Ranking
        
        settings = SiteSettings.get_settings()
        DAILY_LIMIT = settings.daily_upload_limit
        exempt_rank = settings.ranker_limit_exempt_rank
        
        # 랭커 제한 해제 체크
        is_exempt_ranker = False
        if author and exempt_rank > 0:
            # 전체 랭킹에서 현재 사용자 순위 확인
            try:
                current_ranking = Ranking.objects.filter(
                    user=author,
                    period_type=Ranking.PeriodType.ALL
                ).order_by('-period_start').first()
                
                if current_ranking and 0 < current_ranking.rank <= exempt_rank:
                    is_exempt_ranker = True
            except Exception:
                pass
        
        # 제한 체크 (랭커가 아닌 경우에만)
        if not is_exempt_ranker and DAILY_LIMIT > 0:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timezone.timedelta(days=1)
            
            # 오늘 이 카테고리에 올린 게시글 수 체크
            if author:
                # 회원: 사용자 기준
                today_count = Coordinate.objects.filter(
                    author=author,
                    category=category,
                    created_at__gte=today_start,
                    created_at__lt=today_end
                ).count()
            else:
                # 비회원: IP 기준 (세션에 저장)
                client_ip = get_client_ip(request)
                # 세션에 업로드 기록 저장
                upload_key = f'uploads_{category}_{timezone.now().strftime("%Y%m%d")}'
                upload_count = request.session.get(upload_key, 0)
                today_count = upload_count
            
            if today_count >= DAILY_LIMIT:
                category_label = dict(Coordinate.Category.choices).get(category, category)
                messages.error(request, _('오늘 %(category)s 카테고리에 %(limit)s개를 이미 등록했습니다. 내일 다시 시도해주세요.') % {'category': category_label, 'limit': DAILY_LIMIT})
                return render(request, 'coordinates/create.html', {
                    'categories': Coordinate.Category.choices,
                })
        # ===== 제한 체크 끝 =====
        
        # 워터마크 옵션
        watermark_enabled = request.POST.get('watermark_enabled') == 'on'
        watermark_name = request.POST.get('watermark_name', '').strip()

        # 비회원의 경우 워터마크 이름 기본값 설정
        if watermark_enabled and not watermark_name and not author:
            watermark_name = guest_nickname

        coordinate = Coordinate.objects.create(
            author=author,
            title=title,
            postcard_name=postcard_name,
            description=description,
            latitude=latitude,
            longitude=longitude,
            category=category,
            guest_password=hashed_password,
            status=Coordinate.Status.APPROVED,
            approved_at=timezone.now(),
            watermark_enabled=watermark_enabled,
            watermark_name=watermark_name,
        )
        
        # 비회원의 경우 세션에 업로드 기록 저장
        if not author:
            upload_key = f'uploads_{category}_{timezone.now().strftime("%Y%m%d")}'
            current_count = request.session.get(upload_key, 0)
            request.session[upload_key] = current_count + 1
        
        # 이미지 처리
        images = request.FILES.getlist('images')
        for i, image in enumerate(images[:5]):  # 최대 5장
            CoordinateImage.objects.create(
                coordinate=coordinate,
                image=image,
                order=i
            )
        
        # 번역 생성
        from apps.translations.services import translate_on_create
        translate_on_create(coordinate, ['title', 'description', 'postcard_name'])

        # 랭킹 갱신 (회원인 경우)
        if author:
            update_user_ranking(author)

        messages.success(request, _('좌표가 등록되었습니다.'))
        return redirect('coordinates:detail', pk=coordinate.pk)
    
    context = {
        'categories': Coordinate.Category.choices,
    }
    return render(request, 'coordinates/create.html', context)


def coordinate_edit(request, pk):
    """좌표 수정"""
    coordinate = get_object_or_404(Coordinate, pk=pk)
    
    # 권한 확인
    can_edit = False
    if request.user.is_authenticated and coordinate.author == request.user:
        can_edit = True
    
    if request.method == 'POST':
        # 비회원 비밀번호 확인
        if not can_edit and coordinate.guest_password:
            password = request.POST.get('password', '')
            if check_password(password, coordinate.guest_password):
                can_edit = True
        
        if not can_edit:
            messages.error(request, _('수정 권한이 없습니다.'))
            return redirect('coordinates:detail', pk=pk)
        
        coordinate.title = request.POST.get('title', coordinate.title)
        coordinate.postcard_name = request.POST.get('postcard_name', coordinate.postcard_name)
        coordinate.description = request.POST.get('description', coordinate.description)
        coordinate.latitude = request.POST.get('latitude', coordinate.latitude)
        coordinate.longitude = request.POST.get('longitude', coordinate.longitude)
        coordinate.category = request.POST.get('category', coordinate.category)

        # 워터마크 옵션 처리
        old_watermark_enabled = coordinate.watermark_enabled
        coordinate.watermark_enabled = request.POST.get('watermark_enabled') == 'on'
        coordinate.watermark_name = request.POST.get('watermark_name', '').strip()

        coordinate.save()

        # 기존 이미지에 워터마크 적용 (새로 활성화한 경우)
        if coordinate.watermark_enabled and not old_watermark_enabled:
            for img in coordinate.images.all():
                img.coordinate.refresh_from_db()  # DB에서 최신 값 다시 로드
                img._apply_watermark()

        # 이미지 삭제 처리
        delete_image_ids = request.POST.getlist('delete_images')
        if delete_image_ids:
            CoordinateImage.objects.filter(
                pk__in=delete_image_ids,
                coordinate=coordinate
            ).delete()
        
        # 새 이미지 추가 처리
        current_image_count = coordinate.images.count()
        new_images = request.FILES.getlist('images')
        for i, image in enumerate(new_images):
            if current_image_count + i >= 5:  # 최대 5장
                break
            CoordinateImage.objects.create(
                coordinate=coordinate,
                image=image,
                order=current_image_count + i
            )
        
        messages.success(request, _('좌표가 수정되었습니다.'))
        return redirect('coordinates:detail', pk=pk)
    
    context = {
        'coordinate': coordinate,
        'categories': Coordinate.Category.choices,
        'can_edit': can_edit,
    }
    return render(request, 'coordinates/edit.html', context)


def coordinate_delete(request, pk):
    """좌표 삭제"""
    coordinate = get_object_or_404(Coordinate, pk=pk)
    
    can_delete = False
    if request.user.is_authenticated and (coordinate.author == request.user or request.user.is_staff):
        can_delete = True
    
    if request.method == 'POST':
        # 비회원 비밀번호 확인
        if not can_delete and coordinate.guest_password:
            password = request.POST.get('password', '')
            if check_password(password, coordinate.guest_password):
                can_delete = True
        
        if not can_delete:
            messages.error(request, _('삭제 권한이 없습니다.'))
            return redirect('coordinates:detail', pk=pk)
        
        coordinate.delete()
        messages.success(request, _('좌표가 삭제되었습니다.'))
        return redirect('coordinates:list')
    
    return render(request, 'coordinates/delete_confirm.html', {
        'coordinate': coordinate,
        'can_delete': can_delete,
    })


def copy_coords(request, pk):
    """좌표 복사 API - 복사 카운트 증가 (30분 제한)"""
    from django.db.models import F
    import time
    from apps.interactions.models import Notification
    
    coordinate = get_object_or_404(Coordinate, pk=pk)
    
    # 세션에서 마지막 복사 시간 확인 (좌표별로 추적)
    copy_times_key = 'copy_times'
    copy_times = request.session.get(copy_times_key, {})
    
    current_time = time.time()
    last_copy_time = copy_times.get(str(pk), 0)
    time_diff = current_time - last_copy_time
    
    # 30분 = 1800초
    count_incremented = False
    if time_diff >= 1800:
        # 30분이 지났으면 카운트 증가
        old_count = coordinate.copy_count
        Coordinate.objects.filter(pk=pk).update(copy_count=F('copy_count') + 1)
        coordinate.refresh_from_db()
        new_count = coordinate.copy_count
        
        # 마일스톤 알림 (5, 10, 50, 100, 500, 1000)
        milestones = [5, 10, 50, 100, 500, 1000]
        for milestone in milestones:
            if old_count < milestone <= new_count and coordinate.author:
                Notification.objects.create(
                    recipient=coordinate.author,
                    actor=None,
                    notification_type=Notification.NotificationType.COPY_MILESTONE,
                    coordinate=coordinate,
                    message=_("'%(title)s'이(가) 📋 %(milestone)s회 복사되었어요!") % {'title': coordinate.title, 'milestone': milestone}
                )
                break  # 한 번에 하나의 마일스톤만
        
        # 세션에 현재 시간 저장
        copy_times[str(pk)] = current_time
        request.session[copy_times_key] = copy_times
        count_incremented = True
    else:
        coordinate.refresh_from_db()
    
    return JsonResponse({
        'coords': f"{coordinate.latitude}, {coordinate.longitude}",
        'latitude': str(coordinate.latitude),
        'longitude': str(coordinate.longitude),
        'copy_count': coordinate.copy_count,
        'count_incremented': count_incremented,
    })

def map_view(request):
    """지도 탐색 페이지 - Leaflet + OpenStreetMap"""
    import json
    
    # 모든 승인된 좌표 가져오기
    coordinates = Coordinate.objects.filter(status=Coordinate.Status.APPROVED)
    
    # 카테고리 필터
    category = request.GET.get('category', '')
    if category:
        coordinates = coordinates.filter(category=category)
    
    # JSON 데이터 생성
    markers_data = []
    for coord in coordinates:
        first_image = coord.images.first()
        markers_data.append({
            'id': coord.pk,
            'title': coord.title,
            'lat': float(coord.latitude),
            'lng': float(coord.longitude),
            'category': coord.category,
            'category_display': coord.get_category_display(),
            'region': coord.region,
            'region_display': coord.get_region_display(),
            'image': first_image.image.url if first_image else None,
            'copy_count': coord.copy_count,
            'like_count': coord.like_count,
        })
    
    context = {
        'markers_json': json.dumps(markers_data, ensure_ascii=False),
        'categories': Coordinate.Category.choices,
        'category': category,
    }
    return render(request, 'coordinates/map.html', context)
