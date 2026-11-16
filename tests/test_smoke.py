"""스모크 - 주요 화면이 500 없이 떠야 한다

가장 싼 그물이다. 템플릿 문법 오류, 없는 URL 이름, 컨텍스트 프로세서 예외처럼
'페이지 자체가 안 뜨는' 사고는 여기서 전부 걸린다.
"""
from django.urls import reverse

from .base import BaseTest


class PublicPagesTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.coord = self.make_coord()

    def test_주요_페이지가_뜬다(self):
        paths = [
            '/',
            reverse('coordinates:list'),
            reverse('coordinates:map'),
            reverse('coordinates:create'),
            reverse('coordinates:detail', args=[self.coord.pk]),
            reverse('rankings:list'),
            reverse('brag:list'),
            reverse('brag:create'),
            reverse('core:guide'),
            reverse('core:suggestion'),
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_목록_필터와_정렬이_동작한다(self):
        base = reverse('coordinates:list')
        for q in ['?sort=latest', '?sort=oldest', '?sort=likes',
                  '?category=MUSHROOM', '?region=KOREA', '?q=테스트', '?page=1']:
            with self.subTest(query=q):
                self.assertEqual(self.client.get(base + q).status_code, 200)

    def test_없는_글은_404(self):
        self.assertEqual(
            self.client.get(reverse('coordinates:detail', args=[99999])).status_code, 404)

    def test_로그인_페이지가_뜬다(self):
        self.assertEqual(self.client.get('/accounts/login/').status_code, 200)
