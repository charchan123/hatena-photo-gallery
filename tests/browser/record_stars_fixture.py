"""Read-only production inputs and isolated before/after pages; no source mutations."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
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

BASELINE = '4c6b978aebe3ab3e580025b36f74a158c08acb11'
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
    return {'colors': colors, 'total': sum(colors.values())}

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
for variant, module in [('before', before_main), ('after', main)]:
    output = root / variant; output.mkdir(exist_ok=True)
    module.OUTPUT_DIR = str(output)
    module.generate_new_top({r['gallery_name']: [] for r in portal['observations']}, {},
        observation_records=records, research_summary={'case_count': 66}, best_shot_summary={'entry_count': 12})
photos = {}
for row in records[:3]:
    url = row['cover_src'] + '?width=500'
    r = requests.get(url, timeout=20); r.raise_for_status()
    mime = r.headers['content-type'].split(';')[0]; assert mime.startswith('image/')
    name = hashlib.sha256(url.encode()).hexdigest() + '.img'; (root / name).write_bytes(r.content)
    photos[url] = {'file': name, 'mime': mime}
summary = {'baseline': BASELINE, 'published_ref': subprocess.check_output(['git', 'rev-parse', 'origin/gh-pages'], text=True).strip(),
    'records': [{'uri': r['url'], 'title': r['title'], **counts(by_uri[r['url']]), **canonical[r['url']]} for r in records[:3]],
    'photos': photos, 'api_cors_allow_origin': response.headers.get('Access-Control-Allow-Origin'),
    'reference_fetch': 'Public documented entry.json GET; no credentials; total includes repeated names and all colour counts',
    'production_photos': len(portal['observations']), 'data_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('data').glob('*.json'))}}
(root / 'fixture.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print('PASS: isolated original-permalink pages, canonical article URLs, public API counts and thumbnail GET cache')
