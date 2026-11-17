"""운영자 알림 메일 (제보 · 신고)

규칙:
- 제보가 들어오면 바로 1통. 취소하면 안 보낸다.
- 제목은 개조식 - 메일함 목록에서 글 번호·제목·무슨 제보인지가 바로 보인다.
- 본문에 좌표·사진 주소·제보 내용·지금까지 모인 집계가 다 들어간다.
- 메일이 실패해도 제보/신고는 저장돼 있어야 한다. 여기가 핵심이다.
"""
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.urls import reverse

from apps.coordinates.models import Coordinate, NerfReport
from apps.reports.models import Report

from .base import BaseTest


@override_settings(ADMINS=[('Tori', 'admin@example.com')], SITE_URL='https://pikmindiary.com')
class NerfMailTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.owner = self.make_user(nickname='글쓴이')
        self.coord = self.make_coord(author=self.owner, category=Coordinate.Category.BIGFLOWER)
        self.url = reverse('coordinates:toggle_nerf', args=[self.coord.pk])
        mail.outbox = []

    def test_제보가_들어오면_메일_한_통(self):
        self.login(self.make_user(nickname='제보자'))
        self.client.post(self.url, {'kind': 'MUSHROOM'})
        self.assertEqual(len(mail.outbox), 1)

    def test_제목에_글번호와_제목과_제보내용이_들어간다(self):
        self.login(self.make_user(nickname='제보자'))
        self.client.post(self.url, {'kind': 'MUSHROOM'})

        subject = mail.outbox[0].subject
        self.assertIn('핔다', subject)
        self.assertIn('#%d' % self.coord.pk, subject)
        self.assertIn('테스트 좌표', subject)
        self.assertIn('버섯이 됐어요', subject)

    def test_본문에_좌표와_제보자와_집계가_들어간다(self):
        self.login(self.make_user(nickname='제보자'))
        self.client.post(self.url, {'kind': 'MUSHROOM'})

        body = mail.outbox[0].body
        self.assertIn('35.123456', body)
        self.assertIn('129.123456', body)
        self.assertIn('제보자', body)
        self.assertIn('버섯이 됐어요 1명', body)
        self.assertIn('/coordinates/%d/' % self.coord.pk, body)

    def test_사진이_있으면_본문에_사진_주소가_들어간다(self):
        from .base import make_image
        self.coord.images.create(image=make_image())
        self.login(self.make_user())
        self.client.post(self.url, {'kind': 'PHOTO'})

        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('https://pikmindiary.com', html)
        self.assertIn('<img', html)

    def test_제보를_취소하면_메일이_안_간다(self):
        self.login(self.make_user())
        self.client.post(self.url, {'kind': 'MUSHROOM'})
        mail.outbox = []

        self.client.post(self.url, {'kind': 'MUSHROOM'})       # 취소
        self.assertEqual(len(mail.outbox), 0)

    def test_항목을_바꾸면_제보_변경으로_온다(self):
        self.login(self.make_user())
        self.client.post(self.url, {'kind': 'MUSHROOM'})
        mail.outbox = []

        self.client.post(self.url, {'kind': 'SEEDLING'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('제보 변경', mail.outbox[0].subject)
        self.assertIn('모종이 됐어요', mail.outbox[0].subject)

    def test_여러_명이_제보하면_집계가_쌓여서_온다(self):
        for _ in range(2):
            self.client.force_login(self.make_user())
            self.client.post(self.url, {'kind': 'MUSHROOM'})
            self.client.logout()

        self.assertIn('버섯이 됐어요 2명', mail.outbox[-1].body)

    def test_메일이_터져도_제보는_저장된다(self):
        self.login(self.make_user())
        with patch('apps.core.mail.notify_nerf_report', side_effect=RuntimeError('smtp 죽음')):
            res = self.client.post(self.url, {'kind': 'MUSHROOM'})

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['reported'])
        self.assertEqual(NerfReport.objects.count(), 1)

    def test_비회원_제보도_메일이_온다(self):
        self.client.post(self.url, {'kind': 'GONE'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('비회원', mail.outbox[0].body)


@override_settings(ADMINS=[('Tori', 'admin@example.com')], SITE_URL='https://pikmindiary.com')
class ReportMailTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.coord = self.make_coord(author=self.make_user(nickname='글쓴이'))
        mail.outbox = []

    def test_좌표_신고가_들어오면_메일이_온다(self):
        self.login(self.make_user(nickname='신고자'))
        self.client.post(
            reverse('reports:report_coordinate', args=[self.coord.pk]),
            {'reason': 'WRONG_INFO', 'detail': '버섯으로 바뀌었어요'},
        )

        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertIn('신고', m.subject)
        self.assertIn('잘못된 정보', m.subject)
        self.assertIn('신고자', m.subject)
        self.assertIn('버섯으로 바뀌었어요', m.body)
        self.assertIn('35.123456', m.body)

    def test_메일이_터져도_신고는_저장된다(self):
        self.login(self.make_user())
        with patch('apps.core.mail.notify_report', side_effect=RuntimeError('smtp 죽음')):
            self.client.post(
                reverse('reports:report_coordinate', args=[self.coord.pk]),
                {'reason': 'SPAM', 'detail': ''},
            )
        self.assertEqual(Report.objects.count(), 1)
