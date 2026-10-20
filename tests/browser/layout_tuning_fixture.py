"""Read-only, identical production inputs for layout tuning comparisons."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import requests
import main
from best_shot_ui import build_best_shot_model, generate_best_shot_pages
from records_ui import build_observation_records
from research_identifications import split_research_cases

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
baseline = sys.argv[2] if len(sys.argv) > 2 else 'origin/main'
git = lambda ref, name: subprocess.check_output(['git', 'show', f'{ref}:{name}'])
portal = json.loads(git('origin/gh-pages', 'portal-data.json'))
records = build_observation_records(portal)
feature = main.validate_feature_production_state()
assert portal['reference_data']['mushroom_master'] == feature['mushroom_master']
read = lambda name: json.loads(Path(name).read_text())
best_count = build_best_shot_model(read('data/best-shots.json'), portal)['entry_count']
open_cases, _ = split_research_cases(portal, read('data/research-identifications.json'), read('data/mushroom-master.json'))
for variant in ('before', 'after'):
    output = root / variant
    main.OUTPUT_DIR = str(output)
    main._write_feature_page(portal, feature['feature_facets'], str(output), main.ASSETS_DIR, main.safe_filename)
    assert (output / 'features.html').is_file()
    main.generate_new_top({p['gallery_name']: [] for p in portal['observations']}, {},
        observation_records=records, feature_search_available=True,
        research_summary={'case_count': len(open_cases)}, best_shot_summary={'entry_count': best_count})
    generate_best_shot_pages(portal, 'data/best-shots.json', output, Path('assets'))
    if variant == 'before':
        for name in ('portal.css', 'best-shots.css'):
            (output / 'assets' / name).write_bytes(git(baseline, 'assets/' + name))
selected = {e['observation_id'] for e in json.loads(Path('data/best-shots.json').read_text())['entries']}
urls = {p['src'] for p in portal['observations'] if p['observation_id'] in selected}
urls.update(r['cover_src'] + '?width=500' for r in records[:3])
(root / 'photos').mkdir(exist_ok=True)
def cache(url):
    name = 'photos/' + hashlib.sha256(url.encode()).hexdigest() + '.img'
    file = root / name
    if not file.exists():
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        assert response.headers['content-type'].startswith('image/')
        file.write_bytes(response.content)
    return url, {'file': name}
with ThreadPoolExecutor(max_workers=4) as pool:
    photos = dict(pool.map(cache, sorted(urls)))
data = {'baseline': subprocess.check_output(['git', 'rev-parse', baseline], text=True).strip(),
    'published': subprocess.check_output(['git', 'rev-parse', 'origin/gh-pages'], text=True).strip(),
    'photos': photos, 'selections': sorted(selected), 'feature_validator': 'validate_feature_production_state',
    'records': [{'title': r['title'], 'url': r['url']} for r in records[:3]]}
response = requests.get('https://s.hatena.ne.jp/entry.json',
    params=[('uri', r['url']) for r in records[:3]], timeout=20)
response.raise_for_status()
data['star_entries'] = response.json()['entries']
(root / 'fixture.json').write_text(json.dumps(data, ensure_ascii=False, indent=2))
print('PASS: identical production selections/articles, approved features, cached original photographs')
