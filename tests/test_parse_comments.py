# -*- coding: utf-8 -*-
# 不联网的单元测试：python3 -m unittest
import os, sys, unittest

SKILL = os.path.join(os.path.dirname(__file__), '..', 'skills', 'comment-demand-mining')
sys.path.insert(0, os.path.join(SKILL, 'tools'))
import parse_comments as P  # noqa: E402


def load_sample():
    with open(os.path.join(SKILL, 'examples', 'sample-input.txt'), encoding='utf-8') as f:
        data = P.parse_text(f.read())
    data['stats'] = P.build_stats(data)
    return data


class SampleThread(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_sample()
        cls.st = cls.data['stats']
        cls.by_id = {c['id']: c for c in cls.data['comments']}

    def test_post_header(self):
        post = self.data['post']
        self.assertEqual(post['title'], '做独立站选品，AI 给的数据到底能不能信？')
        self.assertEqual(post['date'], '09-01')
        self.assertEqual(post['tags'], ['独立站', '选品', 'AI工具'])

    def test_every_comment_is_parsed(self):
        self.assertEqual(self.data['declared_total'], 14)
        self.assertEqual(self.st['parsed_total'], 14)
        self.assertEqual(self.data['warnings'], [])

    def test_threads_follow_reply_counts(self):
        self.assertEqual((self.st['main'], self.st['replies']), (9, 5))
        self.assertEqual([self.by_id[i]['parent_id'] for i in (2, 3, 4)], [1, 1, 1])
        self.assertEqual(self.by_id[13]['parent_id'], 12)
        self.assertEqual(self.by_id[3]['reply_to'], '做选品的阿青')

    def test_author_pinned_likes_and_regions(self):
        self.assertEqual(self.st['author_comments'], 2)
        self.assertEqual(self.st['pinned_ids'], [1])
        self.assertEqual(self.by_id[1]['likes'], 12000)
        self.assertEqual(self.by_id[4]['likes'], 0)
        self.assertIsNone(self.by_id[14]['region'])
        self.assertEqual(self.st['relative_dates'], 3)

    def test_empty_and_at_only(self):
        self.assertTrue(self.by_id[11]['flags']['empty'])
        self.assertTrue(self.by_id[10]['flags']['at_only'])

    def test_keyword_flags(self):
        asks = [c['id'] for c in self.data['comments'] if c['flags']['ask']]
        self.assertEqual(asks, [4, 5, 6, 14])  # 作者的提问不算；"我也有这个需求"算
        self.assertEqual([c['id'] for c in self.data['comments'] if c['flags']['save']], [9])
        self.assertEqual([c['id'] for c in self.data['comments'] if c['flags']['question']], [4, 14])

    def test_same_nickname_in_two_regions_is_two_people(self):
        # 非作者：小林（2 条算 1 人）、阿杰、上海 momo、北京 momo、官方号、路过、小周、表情包、老卖家、新手小白
        self.assertEqual(self.st['distinct_people'], 10)

    def test_same_account_repeating_itself_is_a_promo_candidate(self):
        self.assertEqual([d['ids'] for d in self.st['duplicates']], [[7, 8]])
        for i in (7, 8):
            self.assertIn('重复发同一句', self.by_id[i]['flags']['promo_hits'])
        self.assertIn('私信', self.by_id[7]['flags']['promo_hits'])


class EdgeCases(unittest.TestCase):
    def test_need_is_not_an_ask(self):
        data = P.parse_text('标题\n05-01\n共 1 条评论\n\n甲\n这个需求很常见\n05-01广东\n赞\n回复\n')
        self.assertFalse(data['comments'][0]['flags']['ask'])

    def test_marketing_is_not_mark(self):
        data = P.parse_text('标题\n05-01\n共 1 条评论\n\n甲\n我对marketing很感兴趣\n05-01广东\n赞\n回复\n')
        self.assertFalse(data['comments'][0]['flags']['save'])

    def test_missing_total_line_warns_but_still_parses(self):
        data = P.parse_text('甲\n你好\n05-01广东\n3\n回复\n')
        self.assertEqual(len(data['comments']), 1)
        self.assertTrue(any('共 N 条评论' in w for w in data['warnings']))

    def test_unexpanded_thread_warns(self):
        text = ('标题\n05-01\n共 9 条评论\n\n'
                '甲\n主楼一\n05-01广东\n5\n3\n\n'
                '乙\n楼中楼\n05-01广东\n赞\n回复\n\n'
                '丙\n主楼二\n05-02广东\n2\n4\n')
        data = P.parse_text(text)
        self.assertTrue(any('声明 3 条楼中楼，只解析到 1 条' in w for w in data['warnings']))
        self.assertEqual(data['comments'][2]['level'], 'main')


if __name__ == '__main__':
    unittest.main()
