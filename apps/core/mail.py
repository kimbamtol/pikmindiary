"""운영자에게 보내는 알림 메일.

왜 스레드로 보내나:
  smtp.naver.com 왕복은 1~3초다. 제보 버튼은 모바일에서 누르는 버튼이라
  그 시간을 사용자가 기다리면 안 된다. 그래서 응답은 바로 내보내고
  메일은 따로 보낸다. 메일이 실패해도 제보는 이미 저장돼 있다.

제목은 개조식으로 짧게 (메일함 목록에서 바로 알아볼 수 있게),
본문은 좌표·사진·제보 내용을 한 화면에 담는다.
"""
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)

SITE_URL = getattr(settings, 'SITE_URL', 'https://pikmindiary.com')


def _admin_addresses():
    return [addr for _name, addr in getattr(settings, 'ADMINS', []) if addr]


def _send(subject, text_body, html_body):
    to = _admin_addresses()
    if not to:
        return
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=getattr(settings, 'SERVER_EMAIL', None),
            to=to,
        )
        if html_body:
            msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
    except Exception:
        # 메일이 안 가도 서비스는 계속 돌아야 한다. 로그만 남긴다.
        logger.exception('운영자 알림 메일 실패: %s', subject)


def notify_admin(subject, text_body, html_body=None):
    """제목·본문을 받아 운영자에게 보낸다. 기본은 백그라운드.

    테스트에서는 메일 백엔드가 locmem 으로 바뀌므로 그때는 바로 보낸다
    (스레드로 보내면 mail.outbox 검사가 들쭉날쭉해진다).
    """
    if 'locmem' in getattr(settings, 'EMAIL_BACKEND', ''):
        _send(subject, text_body, html_body)
        return
    threading.Thread(
        target=_send, args=(subject, text_body, html_body), daemon=True
    ).start()


# ===== 조각 =====

def coord_lines(coordinate):
    """좌표 한 건의 공통 정보 (제목·분류·좌표·링크)"""
    url = f'{SITE_URL}/coordinates/{coordinate.pk}/'
    maps = (f'https://www.google.com/maps/search/?api=1&query='
            f'{coordinate.latitude},{coordinate.longitude}')
    return url, maps


def photo_url(coordinate):
    img = coordinate.images.first()
    if not img:
        return ''
    try:
        return SITE_URL + img.image.url
    except Exception:
        return ''


def _admin_change_url():
    from django.urls import reverse
    try:
        return SITE_URL + reverse('admin_panel:change_list')
    except Exception:
        return SITE_URL


def _admin_report_url():
    from django.urls import reverse
    try:
        return SITE_URL + reverse('admin_panel:report_list')
    except Exception:
        return SITE_URL


def _shell(inner):
    return f"""<html><body style="margin:0;padding:16px;background:#F5F5F5;
font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#212121">
{inner}
<p style="margin:18px 0 0;font-size:12px;color:#9E9E9E">
피크민 다이어리 운영자 알림 · 이 메일은 자동으로 발송됩니다</p>
</body></html>"""


# ===== 제보(엽서 변경) =====

def notify_nerf_report(report, breakdown, changed=False):
    """'사진이 달라요' 제보 1건을 바로 알린다.

    breakdown: [(표시이름, 인원), ...] - 이 글에 지금까지 모인 제보
    changed:   제보자가 고른 항목을 바꾼 경우
    """
    coord = report.coordinate
    kind_label = report.get_change_kind_display()
    who = report.user.nickname if report.user else '비회원'
    who_tag = '회원' if report.user else '비회원'
    url, maps = coord_lines(coord)
    photo = photo_url(coord)
    tally = ' / '.join(f'{name} {n}명' for name, n in breakdown) or '없음'
    head = '제보 변경' if changed else '제보'

    subject = (f'[핔다·{head}] #{coord.pk} {coord.title} · {kind_label}'
               f' · {coord.get_category_display()}')

    text = (
        f'{kind_label}\n'
        f'\n'
        f'글: #{coord.pk} {coord.title} [{coord.get_category_display()}]\n'
        f'좌표: {coord.latitude}, {coord.longitude}\n'
        f'지역: {coord.get_region_display()}\n'
        f'작성자: {coord.author.nickname if coord.author else "비회원"}\n'
        f'\n'
        f'제보자: {who} ({who_tag})\n'
        f'제보 시각: {report.created_at.strftime("%m-%d %H:%M")}\n'
        f'이 글에 모인 제보: {tally}\n'
        f'\n'
        f'글 보기: {url}\n'
        f'지도: {maps}\n'
        f'제보 목록: {_admin_change_url()}\n'
    )

    img_tag = (f'<a href="{url}"><img src="{photo}" alt="" '
               f'style="max-width:260px;border-radius:10px;display:block;margin:12px 0"></a>'
               ) if photo else '<p style="color:#9E9E9E;font-size:13px">사진 없음</p>'

    html = _shell(f"""
<div style="background:#fff;border-radius:12px;padding:18px;max-width:520px">
  <p style="margin:0 0 4px;font-size:20px;font-weight:700">{kind_label}</p>
  <p style="margin:0 0 14px;font-size:13px;color:#757575">
    {who} ({who_tag}) · {report.created_at.strftime('%m-%d %H:%M')}</p>

  <p style="margin:0;font-size:16px;font-weight:700">
    <a href="{url}" style="color:#212121;text-decoration:none">#{coord.pk} {coord.title}</a>
    <span style="font-size:13px;font-weight:400;color:#4CAF50">
      [{coord.get_category_display()}]</span></p>
  <p style="margin:4px 0 0;font-size:14px;font-family:ui-monospace,monospace">
    {coord.latitude}, {coord.longitude}</p>
  <p style="margin:2px 0 0;font-size:13px;color:#757575">
    {coord.get_region_display()} · 작성자
    {coord.author.nickname if coord.author else '비회원'}</p>

  {img_tag}

  <p style="margin:0 0 14px;font-size:13px;color:#757575">
    이 글에 모인 제보: {tally}</p>

  <a href="{_admin_change_url()}" style="display:inline-block;background:#4CAF50;color:#fff;
    text-decoration:none;padding:10px 16px;border-radius:8px;font-size:14px;font-weight:700">
    제보 목록에서 처리</a>
  <a href="{maps}" style="display:inline-block;margin-left:8px;color:#4CAF50;
    text-decoration:none;padding:10px 4px;font-size:14px">지도에서 보기</a>
</div>""")

    notify_admin(subject, text, html)


# ===== 신고 =====

def notify_report(report):
    """신고 1건을 바로 알린다"""
    reason = report.get_reason_display()
    who = report.reporter.nickname if report.reporter else '알 수 없음'

    if report.coordinate:
        target = report.coordinate
        title = f'#{target.pk} {target.title}'
        url, maps = coord_lines(target)
        photo = photo_url(target)
        extra_text = (
            f'좌표: {target.latitude}, {target.longitude}\n'
            f'분류: {target.get_category_display()}\n'
            f'작성자: {target.author.nickname if target.author else "비회원"}\n'
            f'지도: {maps}\n'
        )
        extra_html = (
            f'<p style="margin:4px 0 0;font-size:14px;'
            f'font-family:ui-monospace,monospace">{target.latitude}, {target.longitude}</p>'
            f'<p style="margin:2px 0 0;font-size:13px;color:#757575">'
            f'[{target.get_category_display()}] · 작성자 '
            f'{target.author.nickname if target.author else "비회원"}</p>'
        )
    else:
        c = report.comment
        target = c.coordinate
        title = f'댓글 - {(c.content or "")[:30]}'
        url, maps = coord_lines(target)
        photo = photo_url(target)
        extra_text = (
            f'댓글 내용: {(c.content or "")[:200]}\n'
            f'댓글 작성자: {c.author.nickname if c.author else (c.guest_nickname or "비회원")}\n'
            f'달린 글: #{target.pk} {target.title}\n'
        )
        extra_html = (
            f'<p style="margin:8px 0 0;padding:10px;background:#F5F5F5;border-radius:8px;'
            f'font-size:14px">{(c.content or "")[:200]}</p>'
            f'<p style="margin:4px 0 0;font-size:13px;color:#757575">'
            f'댓글 작성자 {c.author.nickname if c.author else (c.guest_nickname or "비회원")}'
            f' · 달린 글 #{target.pk} {target.title}</p>'
        )

    subject = f'[핔다·신고] {title} · {reason} · {who}'

    text = (
        f'신고 사유: {reason}\n'
        f'신고자: {who}\n'
        f'\n'
        f'대상: {title}\n'
        f'{extra_text}'
        f'\n'
        f'신고 내용: {report.detail or "(없음)"}\n'
        f'\n'
        f'글 보기: {url}\n'
        f'신고 목록: {_admin_report_url()}\n'
    )

    img_tag = (f'<a href="{url}"><img src="{photo}" alt="" '
               f'style="max-width:220px;border-radius:10px;display:block;margin:12px 0"></a>'
               ) if photo else ''

    html = _shell(f"""
<div style="background:#fff;border-radius:12px;padding:18px;max-width:520px;
  border-left:4px solid #C0392B">
  <p style="margin:0 0 4px;font-size:20px;font-weight:700;color:#C0392B">🚨 {reason}</p>
  <p style="margin:0 0 14px;font-size:13px;color:#757575">
    신고자 {who} · {report.created_at.strftime('%m-%d %H:%M')}</p>

  <p style="margin:0;font-size:16px;font-weight:700">
    <a href="{url}" style="color:#212121;text-decoration:none">{title}</a></p>
  {extra_html}
  {img_tag}

  <p style="margin:12px 0;font-size:14px;line-height:1.6">
    <strong>신고 내용</strong><br>{report.detail or '(없음)'}</p>

  <a href="{_admin_report_url()}" style="display:inline-block;background:#C0392B;color:#fff;
    text-decoration:none;padding:10px 16px;border-radius:8px;font-size:14px;font-weight:700">
    신고 목록에서 처리</a>
</div>""")

    notify_admin(subject, text, html)
