"""로그인과 권한

구글 OAuth 자체(구글 서버와의 왕복)는 네트워크가 필요해 자동화하지 않는다.
여기서 지키는 것은 '로그인한 사람과 안 한 사람이 다르게 보이고, 다르게 할 수 있다'는 규칙이다.
"""
from django.urls import reverse

from apps.accounts.models import UserBan

from .base import BaseTest


class LoginStateTest(BaseTest):
    def test_비로그인은_로그인_버튼이_보인다(self):
        html = self.client.get(reverse('coordinates:list')).content.decode()
        self.assertIn('로그인', html)

    def test_로그인하면_로그아웃_버튼이_보인다(self):
        self.login(self.make_user(nickname='밤톨이'))
        html = self.client.get(reverse('coordinates:list')).content.decode()
        self.assertIn('로그아웃', html)

    def test_로그아웃하면_다시_비로그인_상태(self):
        user = self.login(self.make_user(nickname='밤톨이'))
        self.assertIn('로그아웃', self.client.get(reverse('coordinates:list')).content.decode())
        self.client.logout()
        html = self.client.get(reverse('coordinates:list')).content.decode()
        self.assertNotIn('로그아웃', html)

    def test_마이페이지는_로그인이_필요하다(self):
        res = self.client.get('/accounts/mypage/')
        self.assertIn(res.status_code, (302, 403, 404))
        if res.status_code == 302:
            self.assertIn('login', res.url)


class BanTest(BaseTest):
    """차단된 사용자는 미들웨어가 막는다"""

    def test_차단된_회원은_403(self):
        user = self.make_user(nickname='차단대상')
        self.login(user)
        self.assertEqual(self.client.get(reverse('coordinates:list')).status_code, 200)

        UserBan.objects.create(user=user, reason='테스트', is_active=True)
        self.assertEqual(self.client.get(reverse('coordinates:list')).status_code, 403)

    def test_차단_해제하면_다시_들어간다(self):
        user = self.make_user(nickname='차단대상')
        self.login(user)
        ban = UserBan.objects.create(user=user, reason='테스트', is_active=True)
        self.assertEqual(self.client.get(reverse('coordinates:list')).status_code, 403)

        ban.is_active = False
        ban.save()
        self.assertEqual(self.client.get(reverse('coordinates:list')).status_code, 200)
