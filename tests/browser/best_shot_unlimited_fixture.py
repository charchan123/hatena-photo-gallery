"""Generate temporary Best Shot cases and cache public thumbnails by GET only."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import main
import best_shot_ui as current
import requests
from bs4 import BeautifulSoup

BASELINE = 'c3a0420e01a24afe0b86b4eb6c6ee0999c93ad11'
root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
main.OUTPUT_DIR = str(root)
main.copy_shared_assets()
(root / 'screenshots').mkdir(exist_ok=True)
(root / 'photos').mkdir(exist_ok=True)
for filename in ['admin.js', 'admin.css']:
    (root / ('before-' + filename)).write_bytes(subprocess.check_output(['git', 'show', f'{BASELINE}:admin/static/{filename}']))
before = types.ModuleType('before_best_shot')
before.__file__ = current.__file__
exec(compile(subprocess.check_output(['git', 'show', f'{BASELINE}:best_shot_ui.py']).decode(), current.__file__, 'exec'), before.__dict__)
portal = json.loads(subprocess.check_output(['git', 'show', 'origin/gh-pages:portal-data.json']))
# The historical renderer permits only 1–3 selections per month. Compare
# against the same historical configuration, not the admin's newer selections.
baseline_config = json.loads(subprocess.check_output(['git', 'show', f'{BASELINE}:data/best-shots.json']))
old_model = before.build_best_shot_model(baseline_config, portal)
baseline_model = current.build_best_shot_model(baseline_config, portal)
assert old_model == baseline_model
def move_monthly_badges_only(document):
    soup = BeautifulSoup(document, 'html.parser')
    for card in soup.select('.best-shot-grid .best-shot-card'):
        badge = card.select_one('.best-shot-card__body .best-shot-badge')
        if badge:
            card.select_one('.best-shot-photo').insert(0, badge.extract())
    return str(soup)

def without_shared_gallery_additions(document):
    # Validate each new caption and exact shared dependency before comparing
    # the entire remaining document against the historical renderer.
    from gallery_dependencies import BEST_SHOT_LIGHTGALLERY_TAGS
    dependencies = BEST_SHOT_LIGHTGALLERY_TAGS
    assert document.count(dependencies) == 1
    soup = BeautifulSoup(document.replace(dependencies, ''), 'html.parser')
    for card in soup.select('.best-shot-card'):
        link = card.select_one('.best-shot-photo')
        caption = BeautifulSoup(link['data-sub-html'], 'html.parser')
        assert caption.h4.text == card.h3.text
        for field in card.select('.best-shot-meta, .best-shot-comment'):
            assert field.text in caption.get_text()
        del link['data-sub-html']
    return re.sub(r'>\s+<', '><', str(soup))


def comparable_before(document):
    return re.sub(r'>\s+<', '><', move_monthly_badges_only(document))


assert comparable_before(before.render_best_shot_page(old_model)) == without_shared_gallery_additions(current.render_best_shot_page(baseline_model))
for old, new in zip(old_model['years'], baseline_model['years']):
    assert comparable_before(before.render_best_shot_year_page(old)) == without_shared_gallery_additions(current.render_best_shot_year_page(new))

# Independently validate the actual PR configuration with the current code.
config = json.loads(Path('data/best-shots.json').read_text())
new_model = current.build_best_shot_model(config, portal)
assert new_model['entry_count'] == len(config['entries'])


def site(module, name, cfg, observations):
    output = root / name
    output.mkdir(exist_ok=True)
    assets = output / 'assets'
    if not assets.exists():
        assets.symlink_to(root / 'assets', target_is_directory=True)
    path = output / 'fixture-config.json'
    path.write_text(json.dumps(cfg, ensure_ascii=False))
    return module.generate_best_shot_pages(observations, path, output, Path('assets'))


site(before, 'before-public', baseline_config, portal)
site(current, 'after-public', baseline_config, portal)
site(current, 'current-public', config, portal)
photo_urls = sorted({r['src'] for y in new_model['years'] for m in y['months'] for r in m['entries']})


def cache_photo(url):
    error = None
    for _ in range(2):
        try:
            response = requests.get(url, params={'width': '400'}, timeout=(10, 20))
            response.raise_for_status()
            mime = response.headers.get('content-type', '').split(';')[0]
            if not mime.startswith('image/'):
                raise ValueError('public thumbnail is not an image')
            name = hashlib.sha256(url.encode()).hexdigest() + '.img'
            (root / 'photos' / name).write_bytes(response.content)
            return url, {'file': 'photos/' + name, 'mime': mime}
        except (requests.RequestException, ValueError) as exc:
            error = exc
    raise RuntimeError('Read-only public thumbnail retrieval failed') from error


with ThreadPoolExecutor(max_workers=4) as pool:
    photos = dict(pool.map(cache_photo, photo_urls))
(root / 'photo-map.json').write_text(json.dumps(photos))
cases = []
for count in [1, 3, 4, 10, 30, 35]:
    rows = [{'observation_id': f'fixture-{i}', 'gallery_name': f'隔離テスト写真 {i}',
             'src': f'https://fixture-photos.example.test/{i}.svg',
             'capture': {'date': f'2026-10-{i % 28 + 1:02d}'},
             'article': {'title': '隔離した観察記録', 'url': 'https://example.test/entry/fixture'}}
            for i in range(1, count + 1)]
    rows += [{'observation_id': 'september', 'gallery_name': '9月の写真', 'src': 'https://fixture-photos.example.test/sep.svg', 'capture': {'date': '2026-09-01'}},
             {'observation_id': 'older', 'gallery_name': '過去の年の写真', 'src': 'https://fixture-photos.example.test/old.svg', 'capture': {'date': '2025-12-01'}}]
    entries = [{'selection_id': f'best-fixture-{i}', 'observation_id': f'fixture-{i}',
                'comment': f'順序{i}：選んだ理由。' + ('長いコメントの折り返し確認。' * 6 if i % 3 == 0 else ''), 'order': i}
               for i in range(1, count + 1)]
    entries += [{'selection_id': 'september', 'observation_id': 'september', 'comment': '月別グループを維持', 'order': 1},
                {'selection_id': 'older', 'observation_id': 'older', 'comment': '年別グループを維持', 'order': 1}]
    cfg = {'version': 1, 'entries': list(reversed(entries)), 'annual_best': {'2026': f'best-fixture-{count}', '2025': 'older'}}
    model = site(current, f'month-{count}', cfg, {'version': 1, 'observations': rows})
    assert model['years'][0]['entry_count'] == count + 1
    cases.append({'count': count, 'ordered_ids': [f'best-fixture-{i}' for i in range(1, count + 1)], 'annual': f'best-fixture-{count}'})
summary = {'baseline': BASELINE, 'published_ref': subprocess.check_output(['git', 'rev-parse', 'origin/gh-pages'], text=True).strip(),
           'published_photos': len(portal['observations']), 'best_shots': len(config['entries']),
           'selection_ids': [e['selection_id'] for e in config['entries']], 'annual_best': config['annual_best'],
           'selected_years': [y['year'] for y in new_model['years']],
           'config_sha256': hashlib.sha256(Path('data/best-shots.json').read_bytes()).hexdigest(),
           'published_model_identical': True, 'published_html_change_only': 'monthly_badge_moved_into_photo_link', 'cached_public_thumbnails': len(photos), 'cases': cases}
(root / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print('PASS: historical Best Shot model/HTML unchanged; current selections and isolated month cases 1/3/4/10/30/35 generated')
