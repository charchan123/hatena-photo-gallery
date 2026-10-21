"""Independent read-only source hashes and published ID/URL/reference audit."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from best_shot_ui import build_best_shot_model
from research_identifications import split_research_cases

root = Path(__file__).resolve().parents[2]
git = lambda *args: subprocess.check_output(['git', *args], cwd=root)
digest = lambda b: hashlib.sha256(b).hexdigest()
main = git('rev-parse', 'origin/main').decode().strip()
published = git('rev-parse', 'origin/gh-pages').decode().strip()
paths = git('ls-tree', '-r', '--name-only', 'origin/main').decode().splitlines()
protected = [p for p in paths if p.startswith(('data/', 'sync-migrations/', 'admin/'))
    or p.endswith('.py') and not p.startswith(('tests/', 'audit/'))
    or p in ('.github/workflows/generate.yml', 'assets/record-stars.js', 'assets/record-stars.css',
             'assets/update-notices.js', 'assets/update-notices.css')]
hashes = {}
for name in protected:
    before = git('show', 'origin/main:' + name)
    after = (root / name).read_bytes()
    assert before == after, name
    hashes[name] = digest(after)
raw = git('show', 'origin/gh-pages:portal-data.json')
portal = json.loads(raw)
read = lambda name: json.loads((root / name).read_text())
config = read('data/best-shots.json')
model = build_best_shot_model(config, portal)
open_cases, identified = split_research_cases(portal, read('data/research-identifications.json'), read('data/mushroom-master.json'))
retired = read('sync-migrations/hatena-draft-photo-retirement-2026-10-12.json')['observations']
ids = {p['observation_id'] for p in portal['observations']}
urls = {digest(p['src'].encode()) for p in portal['observations']}
assert len(ids) == len(portal['observations']) == 933
assert model['entry_count'] == len(config['entries']) == 16
assert len(open_cases) == 66
assert all(r['observation_id'] not in ids and r['image_url_sha256'] not in urls for r in retired)
assert len(retired) == 7
assert portal['reference_data']['mushroom_master'] == read('data/mushroom-master.json')
assert portal['reference_data']['sources'] == read('data/sources.json')
report = {'main': main, 'gh_pages': published, 'protected_file_count': len(hashes),
    'protected_sha256': hashes, 'portal_sha256': digest(raw),
    'observations_sha256': digest(json.dumps(portal['observations'], sort_keys=True, ensure_ascii=False).encode()),
    'id_url_pairs_sha256': digest(json.dumps(sorted((p['observation_id'], p['src']) for p in portal['observations'])).encode()),
    'counts': {'photos': len(ids), 'best_shots': model['entry_count'], 'notices': len(read('data/update-notices.json')['events']),
        'research_open': len(open_cases), 'research_identified': len(identified), 'retired_excluded': len(retired),
        'master': len(read('data/mushroom-master.json')['entries']), 'sources': len(read('data/sources.json')['sources'])},
    'selection_ids': [e['selection_id'] for e in config['entries']], 'annual_best': config['annual_best'],
    'result': 'PASS', 'writes_to_production': False}
print(json.dumps(report, ensure_ascii=False, indent=2))
