from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import FarmingJournal, FarmingRequest, FarmingParticipation, FarmingJournalLike


def farming_home(request):
    """농사 게시판 메인 페이지"""
    recent_journals = FarmingJournal.objects.all()[:5]
    recent_requests = FarmingRequest.objects.filter(status='open')[:5]
    
    context = {
        'recent_journals': recent_journals,
        'recent_requests': recent_requests,
    }
    return render(request, 'farming/home.html', context)


def journal_list(request):
    """농사 일지 목록"""
    journals = FarmingJournal.objects.all()
    
    # 꽃 종류 필터
    flower_type = request.GET.get('flower')
    if flower_type:
        journals = journals.filter(flower_type=flower_type)
    
    # 페이지네이션
    paginator = Paginator(journals, 12)
    page = request.GET.get('page', 1)
    journals = paginator.get_page(page)
    
    context = {
        'journals': journals,
        'flower_type': flower_type,
    }
    return render(request, 'farming/journal_list.html', context)


from django.contrib.auth.hashers import make_password, check_password


def journal_create(request):
    """농사 일지 작성"""
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        location_name = request.POST.get('location_name', '')
        flower_type = request.POST.get('flower_type', '')
        flower_count = int(request.POST.get('flower_count') or 0)
        
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
                return render(request, 'farming/journal_create.html', {})
            author = None
            hashed_password = make_password(guest_password)

        journal = FarmingJournal(
            author=author,
            guest_nickname=guest_nickname,
            guest_password=hashed_password,
            title=title,
            content=content,
            location_name=location_name,
            flower_type=flower_type,
            flower_count=flower_count,
        )

        # 좌표 처리
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        if lat and lng:
            journal.latitude = lat
            journal.longitude = lng

        # 이미지 처리
        if 'image' in request.FILES:
            journal.image = request.FILES['image']

        journal.save()

        messages.success(request, _('농사 일지가 등록되었습니다!'))
        return redirect('farming:journal_detail', pk=journal.pk)
    
    context = {}
    return render(request, 'farming/journal_create.html', context)


def journal_detail(request, pk):
    """농사 일지 상세"""
    journal = get_object_or_404(FarmingJournal, pk=pk)
    
    # 사용자가 좋아요 했는지 확인
    user_liked = False
    if request.user.is_authenticated:
        user_liked = journal.likes.filter(user=request.user).exists()
    else:
        liked_journals = request.session.get('liked_journals', [])
        user_liked = pk in liked_journals
    
    # 댓글 가져오기
    from apps.comments.models import Comment
    comments = Comment.objects.filter(
        farming_journal=journal,
        is_deleted=False,
        parent__isnull=True
    ).select_related('author').prefetch_related('replies')
    
    context = {
        'journal': journal,
        'user_liked': user_liked,
        'comments': comments,
    }
    return render(request, 'farming/journal_detail.html', context)


@require_POST
def toggle_journal_like(request, pk):
    """농사 일지 좋아요 토글"""
    journal = get_object_or_404(FarmingJournal, pk=pk)
    
    # 본인 글은 좋아요 불가
    if request.user.is_authenticated and journal.author == request.user:
        return JsonResponse({'error': _('본인 글에는 좋아요를 누를 수 없습니다.')}, status=400)
    
    if request.user.is_authenticated:
        # 로그인 사용자: DB에서 관리
        like, created = FarmingJournalLike.objects.get_or_create(
            user=request.user,
            journal=journal
        )
        
        if not created:
            like.delete()
            journal.like_count = max(0, journal.like_count - 1)
            liked = False
        else:
            journal.like_count += 1
            liked = True
    else:
        # 비회원: 세션으로 관리
        liked_journals = request.session.get('liked_journals', [])
        
        if pk in liked_journals:
            liked_journals.remove(pk)
            journal.like_count = max(0, journal.like_count - 1)
            liked = False
        else:
            liked_journals.append(pk)
            journal.like_count += 1
            liked = True
        
        request.session['liked_journals'] = liked_journals
    
    journal.save(update_fields=['like_count'])
    
    # 작성자 랭킹 업데이트
    if journal.author:
        from apps.rankings.utils import update_user_ranking
        update_user_ranking(journal.author)
    
    return JsonResponse({
        'liked': liked,
        'like_count': journal.like_count,
    })


def request_list(request):
    """농사 요청 목록"""
    requests_qs = FarmingRequest.objects.all()
    
    # 상태 필터
    status = request.GET.get('status')
    if status:
        requests_qs = requests_qs.filter(status=status)
    else:
        # 기본: 모집중만 표시
        requests_qs = requests_qs.filter(status='open')
    
    # 꽃 종류 필터
    flower_type = request.GET.get('flower')
    if flower_type:
        requests_qs = requests_qs.filter(flower_type=flower_type)
    
    # 페이지네이션
    paginator = Paginator(requests_qs, 12)
    page = request.GET.get('page', 1)
    requests_qs = paginator.get_page(page)
    
    context = {
        'requests': requests_qs,
        'status': status,
        'flower_type': flower_type,
        'status_choices': FarmingRequest.STATUS_CHOICES,
    }
    return render(request, 'farming/request_list.html', context)


def request_create(request):
    """농사 요청 작성"""
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        location_name = request.POST.get('location_name')
        flower_type = request.POST.get('flower_type', 'any')
        
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
                return render(request, 'farming/request_create.html', {})
            author = None
            hashed_password = make_password(guest_password)
        
        farming_request = FarmingRequest(
            author=author,
            guest_nickname=guest_nickname,
            guest_password=hashed_password,
            title=title,
            content=content,
            latitude=latitude,
            longitude=longitude,
            location_name=location_name,
            flower_type=flower_type,
        )
        
        # 마감 시간 처리
        deadline = request.POST.get('deadline')
        if deadline:
            farming_request.deadline = deadline
        
        farming_request.save()

        messages.success(request, _('농사 요청이 등록되었습니다!'))
        return redirect('farming:request_detail', pk=farming_request.pk)
    
    context = {}
    return render(request, 'farming/request_create.html', context)


def request_detail(request, pk):
    """농사 요청 상세"""
    farming_request = get_object_or_404(FarmingRequest, pk=pk)
    participations = farming_request.participations.all()
    
    # 현재 사용자가 참여했는지 확인
    user_participated = False
    if request.user.is_authenticated:
        user_participated = participations.filter(participant=request.user).exists()
    
    context = {
        'request': farming_request,
        'participations': participations,
        'user_participated': user_participated,
    }
    return render(request, 'farming/request_detail.html', context)


@login_required
def participate(request, pk):
    """농사 참여하기"""
    farming_request = get_object_or_404(FarmingRequest, pk=pk)
    
    if request.method == 'POST':
        # 이미 참여했는지 확인
        existing = FarmingParticipation.objects.filter(
            request=farming_request,
            participant=request.user
        ).first()
        
        if existing:
            messages.warning(request, _('이미 참여하셨습니다.'))
        else:
            FarmingParticipation.objects.create(
                request=farming_request,
                participant=request.user,
                message=request.POST.get('message', '')
            )
            # 상태를 진행중으로 변경
            if farming_request.status == 'open':
                farming_request.status = 'in_progress'
                farming_request.save()
            
            messages.success(request, _('참여해주셔서 감사합니다! 🌸'))
    
    return redirect('farming:request_detail', pk=pk)


@login_required
def complete_request(request, pk):
    """농사 요청 완료 처리"""
    farming_request = get_object_or_404(FarmingRequest, pk=pk)
    
    # 작성자만 완료 가능
    if farming_request.author != request.user:
        messages.error(request, _('권한이 없습니다.'))
        return redirect('farming:request_detail', pk=pk)

    farming_request.status = 'completed'
    farming_request.save()
    messages.success(request, _('농사 요청이 완료되었습니다!'))
    
    return redirect('farming:request_detail', pk=pk)


@login_required
def my_farming(request):
    """내 농사 활동"""
    # 내가 쓴 일지
    my_journals = FarmingJournal.objects.filter(author=request.user)
    
    # 내가 올린 요청
    my_requests = FarmingRequest.objects.filter(author=request.user)
    
    # 내가 참여한 농사
    my_participations = FarmingParticipation.objects.filter(participant=request.user)
    
    context = {
        'my_journals': my_journals,
        'my_requests': my_requests,
        'my_participations': my_participations,
    }
    return render(request, 'farming/my_farming.html', context)


def journal_edit(request, pk):
    """농사 일지 수정"""
    journal = get_object_or_404(FarmingJournal, pk=pk)
    
    # 권한 확인
    can_edit = False
    if request.user.is_authenticated and (journal.author == request.user or request.user.is_staff):
        can_edit = True
    
    if request.method == 'POST':
        # 비회원 비밀번호 확인
        if not can_edit and journal.guest_password:
            password = request.POST.get('password', '')
            if check_password(password, journal.guest_password):
                can_edit = True
        
        if not can_edit:
            messages.error(request, _('수정 권한이 없습니다.'))
            return redirect('farming:journal_detail', pk=pk)

        journal.title = request.POST.get('title', journal.title)
        journal.content = request.POST.get('content', journal.content)
        journal.location_name = request.POST.get('location_name', journal.location_name)
        journal.flower_type = request.POST.get('flower_type', journal.flower_type)
        journal.flower_count = int(request.POST.get('flower_count', journal.flower_count) or 0)

        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        if lat and lng:
            journal.latitude = lat
            journal.longitude = lng

        if 'image' in request.FILES:
            journal.image = request.FILES['image']

        journal.save()
        messages.success(request, _('농사 일지가 수정되었습니다.'))
        return redirect('farming:journal_detail', pk=pk)
    
    context = {
        'journal': journal,
        'can_edit': can_edit,
    }
    return render(request, 'farming/journal_edit.html', context)


def journal_delete(request, pk):
    """농사 일지 삭제"""
    journal = get_object_or_404(FarmingJournal, pk=pk)
    
    # 권한 확인
    can_delete = False
    if request.user.is_authenticated and (journal.author == request.user or request.user.is_staff):
        can_delete = True
    
    if request.method == 'POST':
        # 비회원 비밀번호 확인
        if not can_delete and journal.guest_password:
            password = request.POST.get('password', '')
            if check_password(password, journal.guest_password):
                can_delete = True
        
        if not can_delete:
            messages.error(request, _('삭제 권한이 없습니다.'))
            return redirect('farming:journal_detail', pk=pk)

        journal.delete()
        messages.success(request, _('농사 일지가 삭제되었습니다.'))
        return redirect('farming:journal_list')
    
    context = {
        'journal': journal,
        'can_delete': can_delete,
    }
    return render(request, 'farming/journal_delete.html', context)
