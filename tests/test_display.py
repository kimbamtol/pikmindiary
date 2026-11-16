"""디자인 선택과 목록 보기 밀도

둘 다 '다음에 와도 내 선택이 그대로인가'가 핵심이다.
회원은 계정에, 비회원은 쿠키에 저장하므로 양쪽을 다 본다.
"""
import re

from django.urls import reverse

from apps.core.models import SiteSettings

from .base import BaseTest

BODY = re.compile(r'<body[^>]*>')


class DesignToggleTest(BaseTest):
    def setUp(self):
        super().setUp()
        s = SiteSettings.get_settings()
        s.design_beta_enabled = True
        s.save()

    def ui_of(self, path=None):
        html = self.client.get(path or reverse('coordinates:list')).content.decode()
        tag = BODY.search(html).group(0)
        return 'notebook' if 'data-ui="notebook"' in tag else 'classic'

    def test_처음_온_사람은_수첩_디자인을_본다(self):
        self.assertEqual(self.ui_of(), 'notebook')

    def test_기존_디자인으로_바꾸면_유지된다(self):
        self.client.get(reverse('core:design_beta_off') + '?next=/coordinates/')
        self.assertEqual(self.ui_of(), 'classic')
        self.assertEqual(self.ui_of(), 'classic')      # 다음 요청에도 그대로

    def test_다시_수첩으로_되돌린다(self):
        self.client.get(reverse('core:design_beta_off') + '?next=/coordinates/')
        self.client.get(reverse('core:design_beta_on') + '?next=/coordinates/')
        self.assertEqual(self.ui_of(), 'notebook')

    def test_사이트_설정을_끄면_모두_기존_디자인(self):
        s = SiteSettings.get_settings()
        s.design_beta_enabled = False
        s.save()
        self.assertEqual(self.ui_of(), 'classic')
        self.assertNotIn('beta-toggle',
                         self.client.get(reverse('coordinates:list')).content.decode())

    def test_투표_주소는_사라졌다(self):
        self.assertEqual(self.client.post('/design/vote/', {'choice': 'NEW'}).status_code, 404)
        self.assertEqual(self.client.post('/design/popup/dismiss/').status_code, 404)

    def test_팝업과_투표_띠가_화면에_없다(self):
        html = self.client.get(reverse('coordinates:list')).content.decode()
        self.assertNotIn('betaPopup', html)
        self.assertNotIn('betaVoteBar', html)


class DensityTest(BaseTest):
    def test_비회원은_쿠키에_저장된다(self):
        res = self.client.post(reverse('core:set_list_density'), {'density': 'dense'})
        self.assertIn(res.status_code, (200, 302))
        self.assertEqual(self.client.cookies['pd_density'].value, 'dense')

        html = self.client.get(reverse('coordinates:list')).content.decode()
        self.assertIn('data-density="dense"', html)

    def test_회원은_계정에_저장된다(self):
        user = self.login(self.make_user())
        self.client.post(reverse('core:set_list_density'), {'density': 'large'})

        user.refresh_from_db()
        self.assertEqual(user.list_density, 'large')

        # 쿠키를 버려도 계정 설정이 살아 있다
        self.client.cookies.clear()
        self.client.force_login(user)
        html = self.client.get(reverse('coordinates:list')).content.decode()
        self.assertIn('data-density="large"', html)

    def test_이상한_값은_무시된다(self):
        self.client.post(reverse('core:set_list_density'), {'density': '이상한값'})
        html = self.client.get(reverse('coordinates:list')).content.decode()
        self.assertIn('data-density="normal"', html)
