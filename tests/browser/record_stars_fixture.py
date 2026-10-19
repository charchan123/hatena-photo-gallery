"""Read-only production inputs and isolated before/after pages; no source mutations."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import html
import json
import subprocess
import sys
import types
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import requests
from bs4 import BeautifulSoup
import main
from records_ui import build_observation_records

BASELINE = '978ec61c34420ddcb01dfb3d4a6315ea7c03548c'
root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
(root / 'screenshots').mkdir(exist_ok=True)
portal = json.loads(subprocess.check_output(['git', 'show', 'origin/gh-pages:portal-data.json']))
records = build_observation_records(portal)
urls = [r['url'] for r in records[:3]]
assert len(set(urls)) == 3 and all(urlsplit(u).netloc == 'exsudoporus-ruber.hatenablog.jp' for u in urls)
response = requests.get('https://s.hatena.ne.jp/entry.json', params=[('uri', u) for u in urls], timeout=20)
response.raise_for_status()
entry_data = response.json()
by_uri = {e['uri']: e for e in entry_data['entries']}
assert set(by_uri) == set(urls)

def counts(entry):
    def amount(stars):
        values = [s.get('count', 1) for s in stars]
        assert all(type(n) is int and n >= 1 for n in values)
        return sum(values)
    colors = {'yellow': amount(entry['stars'])}
    for color in entry.get('colored_stars', []):
        assert color['color'] not in colors
        colors[color['color']] = amount(color['stars'])
    return {'colors': colors, 'total': sum(colors.values()), 'stars': [dict(name=s['name'], color=color, count=s.get('count', 1)) for color, stars in [('yellow', entry['stars']), *[(c['color'], c['stars']) for c in entry.get('colored_stars', [])]] for s in stars]}

canonical = {}
def fetch_article(url):
    r = requests.get(url, timeout=20); r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    link = soup.select_one('link[rel=canonical]')
    assert link and link.get('href') == url
    return url, {'canonical': link['href'], 'star_container_present': bool(soup.select('.hatena-star-container')), 'status': r.status_code}
with ThreadPoolExecutor(max_workers=3) as pool:
    canonical = dict(pool.map(fetch_article, urls))

before_records = types.ModuleType('before_records_ui')
exec(compile(subprocess.check_output(['git', 'show', BASELINE + ':records_ui.py']), 'records_ui.py', 'exec'), before_records.__dict__)
before_main = types.ModuleType('before_main'); before_main.__file__ = main.__file__; sys.modules['before_main'] = before_main
exec(compile(subprocess.check_output(['git', 'show', BASELINE + ':main.py']), main.__file__, 'exec'), before_main.__dict__)
before_main.render_record_preview_rows = before_records.render_record_preview_rows
best_count = len(json.loads(Path('data/best-shots.json').read_text())['entries'])
research_count = 66
for variant, module in [('before', before_main), ('after', main)]:
    output = root / variant; output.mkdir(exist_ok=True)
    module.OUTPUT_DIR = str(output)
    module.generate_new_top({r['gallery_name']: [] for r in portal['observations']}, {},
        observation_records=records, research_summary={'case_count': research_count}, best_shot_summary={'entry_count': best_count})
photos = {}
for row in records[:3]:
    url = row['cover_src'] + '?width=500'
    r = requests.get(url, timeout=20); r.raise_for_status()
    mime = r.headers['content-type'].split(';')[0]; assert mime.startswith('image/')
    name = hashlib.sha256(url.encode()).hexdigest() + '.img'; (root / name).write_bytes(r.content)
    photos[url] = {'file': name, 'mime': mime}
public_url = 'https://charchan123.github.io/hatena-photo-gallery/new-top.html'
public = requests.get(public_url, timeout=20); public.raise_for_status()
home = requests.get('https://exsudoporus-ruber.hatenablog.jp/', timeout=20); home.raise_for_status()
home_soup = BeautifulSoup(home.text, 'html.parser')
live_site = {'new_top_url': public.url, 'new_top_status': public.status_code,
             'new_top_csp': public.headers.get('Content-Security-Policy'),
             'new_top_x_frame_options': public.headers.get('X-Frame-Options'),
             'home_has_new_top_iframe': any('new-top.html' in (f.get('src') or '') for f in home_soup.select('iframe')),
             'public_new_top_has_star_script': 'record-stars.js' in public.text}
summary = {'live_site': live_site, 'baseline': BASELINE, 'published_ref': subprocess.check_output(['git', 'rev-parse', 'origin/gh-pages'], text=True).strip(),
    'records': [{'uri': r['url'], 'title': r['title'], **counts(by_uri[r['url']]), **canonical[r['url']]} for r in records[:3]],
    'photos': photos, 'api_cors_allow_origin': response.headers.get('Access-Control-Allow-Origin'),
    'reference_fetch': 'Public documented entry.json GET; no credentials; total includes repeated names and all colour counts',
    'production_photos': len(portal['observations']), 'data_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('data').glob('*.json'))}}
(root / 'fixture.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print('PASS: isolated original-permalink pages, canonical article URLs, public API counts and thumbnail GET cache')

# Exact same public, declarative profile-icon interface observed in the original blog HTML.
probe = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Isolated native profile-icon probe</title><script>window.Hatena={Star:{SiteConfig:{entryNodes:{}}}}</script>'
for row in records[:3]:
    probe += ('<article><h2>' + html.escape(row['title']) + '</h2><div class="native-probe" data-hatena-star-container data-hatena-star-url="' + html.escape(row['url'], quote=True) + '" data-hatena-star-title="' + html.escape(row['title'], quote=True) + '" data-hatena-star-variant="profile-icon" data-hatena-star-profile-url-template="https://blog.hatena.ne.jp/{username}/"></div></article>')
probe += '<script src="https://s.hatena.ne.jp/js/widget/star.js" defer></script><script src="https://s.hatena.ne.jp/js/HatenaStar.js" defer></script>'
(root / 'profile-probe.html').write_text(probe)
