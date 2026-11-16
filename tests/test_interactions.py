"""좋아요, 북마크, 좌표 복사, 댓글

좋아요 수 같은 숫자는 모델에 그대로 저장해 두고 뷰에서 직접 올리고 내린다(비정규화).
그래서 '눌렀다 취소하면 원래대로 돌아오는지'를 매번 확인해야 한다.
한 번만 세거나 두 번 세는 사고가 이 구조에서 가장 흔하다.
"""
import json

from django.urls import reverse

from apps.comments.models import Comment
from apps.interactions.models import Bookmark, Like, Notification

from .base import BaseTest


class LikeTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.author = self.make_user(nickname='글쓴이')
        self.coord = self.make_coord(author=self.author)

    def test_회원이_좋아요를_눌렀다_취소한다(self):
        self.login(self.make_user(nickname='독자'))
        url = reverse('interactions:toggle_like', args=[self.coord.pk])

        self.client.post(url)
        self.coord.refresh_from_db()
        self.assertEqual(self.coord.like_count, 1)
        self.assertEqual(Like.objects.count(), 1)

        self.client.post(url)
        self.coord.refresh_from_db()
        self.assertEqual(self.coord.like_count, 0)
        self.assertEqual(Like.objects.count(), 0)

    def test_본인_글에는_좋아요를_못_누른다(self):
        self.login(self.author)
        res = self.client.post(reverse('interactions:toggle_like', args=[self.coord.pk]))
        self.assertEqual(res.status_code, 400)
        self.coord.refresh_from_db()
        self.assertEqual(self.coord.like_count, 0)

    def test_비회원도_좋아요를_누를_수_있고_세션으로_중복이_막힌다(self):
        url = reverse('interactions:toggle_like', args=[self.coord.pk])
        self.client.post(url)
        self.coord.refresh_from_db()
        self.assertEqual(self.coord.like_count, 1)

        self.client.post(url)          # 같은 세션으로 또 누르면 취소다
        self.coord.refresh_from_db()
        self.assertEqual(self.coord.like_count, 0)

    def test_좋아요를_받으면_작성자에게_알림이_간다(self):
        self.login(self.make_user(nickname='독자'))
        self.client.post(reverse('interactions:toggle_like', args=[self.coord.pk]))
        self.assertTrue(Notification.objects.filter(recipient=self.author).exists())


class BookmarkTest(BaseTest):
    def test_북마크를_켰다_끈다(self):
        coord = self.make_coord(author=self.make_user(nickname='글쓴이'))
        self.login(self.make_user(nickname='독자'))
        url = reverse('interactions:toggle_bookmark', args=[coord.pk])

        self.client.post(url)
        self.assertEqual(Bookmark.objects.count(), 1)
        self.client.post(url)
        self.assertEqual(Bookmark.objects.count(), 0)


class CopyTest(BaseTest):
    def test_좌표를_복사하면_복사수가_오른다(self):
        coord = self.make_coord(author=self.make_user())
        res = self.client.get(reverse('coordinates:copy_coords', args=[coord.pk]))

        self.assertEqual(res.status_code, 200)
        body = json.loads(res.content)
        self.assertIn(str(coord.latitude), json.dumps(body, ensure_ascii=False))

        coord.refresh_from_db()
        self.assertEqual(coord.copy_count, 1)


class CommentTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.coord = self.make_coord(author=self.make_user(nickname='글쓴이'))

    def test_회원이_댓글을_단다(self):
        self.login(self.make_user(nickname='댓글러'))
        self.client.post(reverse('comments:create', args=[self.coord.pk]),
                         {'content': '좋은 좌표 감사합니다'})

        self.assertEqual(Comment.objects.count(), 1)
        self.coord.refresh_from_db()
        self.assertEqual(self.coord.comment_count, 1)

    def test_비회원이_닉네임과_비밀번호로_댓글을_단다(self):
        self.client.post(reverse('comments:create', args=[self.coord.pk]), {
            'content': '비회원 댓글', 'guest_nickname': '지나가던', 'guest_password': '비밀1234'})

        c = Comment.objects.get()
        self.assertIsNone(c.author)
        self.assertEqual(c.guest_nickname, '지나가던')
        self.assertNotEqual(c.guest_password, '비밀1234')   # 해시로 저장

    def test_빈_댓글은_저장되지_않는다(self):
        self.login(self.make_user())
        self.client.post(reverse('comments:create', args=[self.coord.pk]), {'content': '   '})
        self.assertEqual(Comment.objects.count(), 0)

    def test_대댓글이_부모를_가리킨다(self):
        self.login(self.make_user(nickname='댓글러'))
        self.client.post(reverse('comments:create', args=[self.coord.pk]), {'content': '원댓글'})
        parent = Comment.objects.get()

        self.client.post(reverse('comments:reply', args=[parent.pk]), {'content': '답글'})
        reply = Comment.objects.exclude(pk=parent.pk).get()
        self.assertEqual(reply.parent, parent)

    def test_작성자만_댓글을_지운다(self):
        self.login(self.make_user(nickname='댓글러'))
        self.client.post(reverse('comments:create', args=[self.coord.pk]), {'content': '내 댓글'})
        comment = Comment.objects.get()

        self.client.logout()
        self.login(self.make_user(nickname='남'))
        self.client.post(reverse('comments:delete', args=[comment.pk]))
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())
