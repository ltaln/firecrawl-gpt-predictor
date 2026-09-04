"""Join Firecrawl pages by explicit fixture links, never by sorted xi position."""
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from run_pipeline import LinkParser, visible_text

SECTIONS = ('mixed_data', 'asian_handicap_changes', 'score_odds_changes',
            'predicted_lineup', 'historical_lineup_ratings')
PATHS = {'/tx/10013.php': SECTIONS[1], '/tx/10017.php': SECTIONS[2],
         '/tx/10016.php': SECTIONS[3], '/tx/10015.php': SECTIONS[4]}


def canonical(url):
    p = urlparse(url)
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path or '/', '',
                       urlencode(sorted((k, v) for k, vs in parse_qs(p.query).items() for v in vs)), ''))


def html_of(record):
    d = record.get('response', {}).get('data', {})
    return d.get('rawHtml') or d.get('html') or ''


def links(record):
    parser = LinkParser()
    parser.feed(html_of(record))
    return {canonical(urljoin(record['url'], u)) for u in parser.links
            if urlparse(urljoin(record['url'], u)).netloc.lower() in {'www.hh520.com', 'hh520.com'}}


def xi_id(url):
    p = urlparse(url)
    value = parse_qs(p.query).get('id', [''])[0]
    return value if p.path == '/xi.php' and value.isdigit() else None


def page_key(url):
    p = urlparse(url)
    q = parse_qs(p.query)
    if p.path in {'/tx/10015.php', '/tx/10016.php'}:
        code = q.get('code', [''])[0]
        if re.fullmatch(r'\d{11}', code):
            return f'{code[:4]}-{code[4:6]}-{code[6:8]}', int(code[8:])
    elif p.path in {'/tx/10013.php', '/tx/10017.php'}:
        date = q.get('date' if p.path.endswith('10013.php') else 'riqi', [''])[0]
        number = q.get('changci', [''])[0]
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) and number.isdigit():
            return date, int(number)
    return None


class RosterParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.in_time = False
        self.fixtures = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'div':
            if not self.depth and {'element', 'match'} <= set(a.get('class', '').split()):
                self.ids, self.time = set(), ''
                self.depth = 1
            elif self.depth:
                self.depth += 1
        if self.depth:
            if tag == 'a' and xi_id(a.get('href', '')):
                self.ids.add(xi_id(a['href']))
            if tag == 'span' and 'time' in a.get('class', '').split():
                self.in_time = True

    def handle_data(self, data):
        if self.depth and self.in_time:
            self.time += data

    def handle_endtag(self, tag):
        if tag == 'span':
            self.in_time = False
        if tag == 'div' and self.depth:
            self.depth -= 1
            if not self.depth:
                number = re.search(r'[:：]\s*(\d+)', self.time)
                if len(self.ids) != 1 or not number:
                    raise ValueError('Ambiguous fixture card in authoritative match list')
                self.fixtures.append((int(number[1]), next(iter(self.ids))))


def roster(records, date):
    candidates = [r for r in records if r.get('category') == 'match_list'
                  and r.get('response', {}).get('success') and html_of(r)
                  and urlparse(r['url']).path in {'', '/'}
                  and parse_qs(urlparse(r['url']).query).get('date') == [date.replace('-', '')]]
    if not candidates:
        raise ValueError('No explicit competition-day match list; refusing positional matching')
    parser = RosterParser()
    parser.feed(html_of(max(candidates, key=lambda r: r.get('fetched_at', ''))))
    fixtures = parser.fixtures
    if not fixtures or len({n for n, _ in fixtures}) != len(fixtures) or len({x for _, x in fixtures}) != len(fixtures):
        raise ValueError('Missing or conflicting fixture identities in match list')
    return fixtures


def normalized_name(value):
    value = re.sub(r'\s+', '', value).casefold()
    # Exact aliases evidenced by xi=6119's explicit links and both lineup
    # backlinks (20260904004). Do not use fuzzy matching for arbitrary teams.
    return {'利雅青年': '利雅得青年人', '利雅得青年': '利雅得青年人',
            '利雅新月': '利雅得新月'}.get(value, value)


def mixed_teams(record):
    header = re.search(r'<h1\b[^>]*>(.*?)</h1>', html_of(record), re.I | re.S)
    match = re.search(r'(.+?)\s+vs\s+(.+?)(?:。|$)', visible_text(header[1]) if header else '', re.I)
    return tuple(normalized_name(x) for x in match.groups()) if match else None


class FixtureAnchorParser(HTMLParser):
    def __init__(self, xi):
        super().__init__()
        self.xi, self.active, self.label, self.pairs = xi, False, '', set()

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.active = xi_id(dict(attrs).get('href', '')) == self.xi
            self.label = ''

    def handle_data(self, data):
        if self.active:
            self.label += data

    def handle_endtag(self, tag):
        if tag == 'a' and self.active:
            pair = re.fullmatch(r'\s*(.+?)\s+vs\s+(.+?)\s*', self.label, re.I)
            if pair:
                self.pairs.add(tuple(normalized_name(x) for x in pair.groups()))
            self.active = False


def anchor_teams(record, xi):
    parser = FixtureAnchorParser(xi)
    parser.feed(html_of(record))
    return parser.pairs


def check_page(record, category, xi, teams):
    data = record.get('response', {}).get('data', {})
    if not record.get('response', {}).get('success') or not html_of(record) or not data.get('markdown', '').strip():
        return 'Missing Firecrawl content'
    text = visible_text(html_of(record))
    flat = re.sub(r'\s+', ' ', text)
    key = page_key(record['url'])
    if not key:
        return 'Invalid page identity URL'
    day, number = key
    if category in {'predicted_lineup', 'historical_lineup_ratings'}:
        backlinks = {xi_id(u) for u in links(record) if xi_id(u)}
        if backlinks != {xi}:
            return 'Lineup xi backlink conflict or missing backlink'
        if len(anchor_teams(record, xi)) != 1:
            return 'Missing or ambiguous lineup fixture team label'
        if not re.search(rf'日期\s*[:：]\s*{re.escape(day)}\s*场次\s*[:：]\s*{number}(?!\d)', flat):
            return 'Lineup header does not match its code'
    elif category == 'asian_handicap_changes':
        header = re.search(r'场次\s*(\d+)\s*[·•]\s*(.+?)\s+vs\s+([^\n]+?)(?=\s*比分\s*[:：]|\n|$)', text, re.I)
        if not header or int(header[1]) != number or f'日期：{day}' not in flat.replace('日期: ', '日期：'):
            return 'Missing/mismatched handicap fixture header (possibly a no-data page)'
        if tuple(normalized_name(x) for x in header.groups()[1:]) not in teams:
            return 'Handicap home/away teams conflict'
    elif category == 'score_odds_changes':
        header = re.search(r'主队\s*[:：]\s*(.+?)\s+vs\s+客队\s*[:：]\s*([^\n|]+)', text, re.I)
        if not header or not re.search(rf'{re.escape(day)}\s*第\s*{number}\s*场', flat):
            return 'Missing/mismatched score-odds fixture header'
        if tuple(normalized_name(x) for x in header.groups()) not in teams:
            return 'Score-odds home/away teams conflict'
    return None


def assemble(records, date):
    """Competition-day roster includes overnight kickoffs; no kickoff-date filter."""
    by_url = {}
    for r in sorted(records, key=lambda r: r.get('fetched_at', '')):
        by_url[canonical(r['url'])] = r
    mixed = {xi_id(r['url']): r for r in by_url.values() if r.get('category') == 'mixed_data' and xi_id(r['url'])}
    fixtures = roster(records, date)
    joined = []
    for number, xi in fixtures:
        mix = mixed.get(xi)
        if mix is None:
            raise ValueError(f'No Firecrawl mixed page for roster xi={xi}')
        teams = mixed_teams(mix)
        errors, evidence = [], {}
        if not teams or not mix.get('response', {}).get('success') or not mix['response']['data'].get('markdown', '').strip():
            errors.append('Mixed page has no valid team identity/content')
        pages = {'mixed_data': mix}
        targets = {}
        for url in links(mix):
            category = PATHS.get(urlparse(url).path)
            if category:
                targets.setdefault(category, set()).add(url)
        # Team aliases are accepted only when BOTH lineup pages explicitly link
        # to this xi, match their own header/code and corroborate the same pair.
        team_pairs = {teams} if teams else set()
        aliases = []
        for category in ('predicted_lineup', 'historical_lineup_ratings'):
            urls = targets.get(category, set())
            candidate = by_url.get(next(iter(urls))) if len(urls) == 1 else None
            if candidate and not check_page(candidate, category, xi, team_pairs):
                aliases.append(anchor_teams(candidate, xi))
        if len(aliases) == 2 and all(aliases):
            corroborated = aliases[0] & aliases[1]
            if not corroborated:
                errors.append('Lineup pages disagree on the fixture team pair')
            team_pairs.update(corroborated)
        score_key = None
        for category in SECTIONS[1:]:
            urls = targets.get(category, set())
            if len(urls) != 1:
                errors.append(f'{category}: missing or ambiguous explicit link')
                continue
            url = next(iter(urls))
            if category == 'score_odds_changes':
                score_key = page_key(url)
            page = by_url.get(url)
            if not page:
                errors.append(f'{category}: linked Firecrawl page not collected')
                continue
            pages[category] = page
            error = check_page(page, category, xi, team_pairs)
            evidence[category] = {'url': page['url'], 'result': 'FAIL' if error else 'PASS', 'error': error}
            if error:
                errors.append(f'{category}: {error}')
        if not score_key or score_key[1] != number:
            errors.append('Roster number conflicts with explicitly linked score page')
        code = f'{score_key[0].replace("-", "")}{score_key[1]:03d}' if score_key else f'unresolved-xi-{xi}'
        kickoff = re.search(r'\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}', visible_text(html_of(mix)))
        joined.append({'match_no': number, 'xi': xi, 'code': code, 'pages': pages,
                       'kickoff_at_raw': kickoff[0] if kickoff else None,
                       'identity_check': {'result': 'FAIL' if errors else 'PASS', 'errors': errors,
                                          'verified_team_pairs': sorted(team_pairs), 'evidence': evidence}})
    selected = {x for _, x in fixtures}
    return joined, [{'xi': x, 'url': r['url'], 'reason': 'Not in requested competition-day roster; raw data retained'}
                    for x, r in mixed.items() if x not in selected]
