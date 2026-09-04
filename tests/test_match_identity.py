import copy
import unittest

from match_identity import assemble, PATHS

BASE = 'https://www.hh520.com'
DAY = '2026-09-04'


def record(url, category, html):
    return {'url': BASE + url, 'category': category, 'fetched_at': '2026-09-04T00:00:00Z',
            'response': {'success': True, 'data': {'rawHtml': html, 'markdown': html}}}


def fixture():
    urls = ['/tx/10013.php?date=2026-09-04&changci=1',
            '/tx/10017.php?riqi=2026-09-04&changci=1',
            '/tx/10016.php?code=20260904001', '/tx/10015.php?code=20260904001']
    roster = '<div class="element match"><a href="/xi.php?id=900"></a><span class="time">周五 : 1</span></div>'
    mixed = '<h1>甲队 VS 乙队。2026年9月5日。比赛概览</h1><p>2026-09-05 00:30</p>'
    mixed += ''.join(f'<a href="{url}">数据</a>' for url in urls)
    lineup = '<a href="/xi.php?id=900">甲队 VS 乙队</a><p>日期：2026-09-04 场次：1</p><table><tr><td>阵容数据</td></tr></table>'
    htmls = ['<h1>场次 1 · 甲队 vs 乙队 比分: 0:2</h1><p>日期：2026-09-04</p>',
             '<p>2026-09-04 第 1 场</p><p>主队：甲队 VS 客队：乙队 | 时间：00:30</p>', lineup, lineup]
    return [record('/?date=20260904', 'match_list', roster), record('/xi.php?id=900', 'mixed_data', mixed)] + [
        record(url, PATHS[url.split('?')[0]], html) for url, html in zip(urls, htmls)]


class IdentityTests(unittest.TestCase):
    def passed(self, records):
        joined, _ = assemble(records, DAY)
        return joined[0]['identity_check']['result'] == 'PASS'

    def test_overnight_is_preserved(self):
        joined, _ = assemble(fixture(), DAY)
        self.assertEqual(joined[0]['kickoff_at_raw'], '2026-09-05 00:30')
        self.assertEqual(joined[0]['code'], '20260904001')
        self.assertTrue(self.passed(fixture()))

    def test_reordering_does_not_change_identity(self):
        self.assertTrue(self.passed(list(reversed(fixture()))))

    def test_unrelated_lower_xi_not_assigned_a_fake_code(self):
        records = fixture() + [record('/xi.php?id=1', 'mixed_data', '<h1>其他比赛</h1>')]
        joined, unassigned = assemble(records, DAY)
        self.assertEqual([x['xi'] for x in joined], ['900'])
        self.assertEqual([x['xi'] for x in unassigned], ['1'])

    def test_case_duplicate_not_an_extra_match(self):
        records = fixture()
        duplicate = copy.deepcopy(records[1])
        duplicate['url'] = duplicate['url'].replace('www.hh520.com', 'WWW.HH520.COM')
        joined, _ = assemble(records + [duplicate], DAY)
        self.assertEqual(len(joined), 1)

    def test_missing_page_fails(self):
        self.assertFalse(self.passed(fixture()[:-1]))

    def test_same_number_other_day_not_substituted(self):
        records = fixture()
        records[2]['url'] = records[2]['url'].replace('2026-09-04', '2026-09-03')
        self.assertFalse(self.passed(records))

    def test_wrong_lineup_xi_fails(self):
        records = fixture()
        records[-1]['response']['data']['rawHtml'] = records[-1]['response']['data']['rawHtml'].replace('id=900', 'id=901')
        self.assertFalse(self.passed(records))

    def test_reversed_teams_fail(self):
        records = fixture()
        records[3]['response']['data']['rawHtml'] = '<p>2026-09-04 第 1 场</p><p>主队：乙队 VS 客队：甲队</p>'
        self.assertFalse(self.passed(records))

    def test_no_data_stub_fails(self):
        records = fixture()
        records[2]['response']['data']['rawHtml'] = '<p>没有找到日期 2026-09-04 场次 1 的任何数据。</p>'
        self.assertFalse(self.passed(records))

    def test_empty_markdown_fails(self):
        records = fixture()
        records[2]['response']['data']['markdown'] = ''
        self.assertFalse(self.passed(records))

    def test_ambiguous_link_fails(self):
        records = fixture()
        records[1]['response']['data']['rawHtml'] += '<a href="/tx/10016.php?code=20260904002">冲突</a>'
        self.assertFalse(self.passed(records))

    def test_wrong_header_number_fails(self):
        records = fixture()
        records[-1]['response']['data']['rawHtml'] = records[-1]['response']['data']['rawHtml'].replace('场次：1', '场次：2')
        self.assertFalse(self.passed(records))

    def test_no_explicit_roster_fails_closed(self):
        records = fixture()
        records[0]['url'] = BASE + '/'
        with self.assertRaises(ValueError):
            assemble(records, DAY)

    def test_missing_roster_match_fails_closed(self):
        records = fixture()
        records[0]['response']['data']['rawHtml'] = records[0]['response']['data']['rawHtml'].replace('id=900', 'id=901')
        with self.assertRaises(ValueError):
            assemble(records, DAY)

    def test_conflicting_lineup_team_pair_fails(self):
        records = fixture()
        records[-1]['response']['data']['rawHtml'] = records[-1]['response']['data']['rawHtml'].replace('甲队 VS 乙队', '丙队 VS 丁队')
        self.assertFalse(self.passed(records))


if __name__ == '__main__':
    unittest.main()
