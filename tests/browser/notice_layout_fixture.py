"""Isolated real portal generator fixtures; never edits production notices/data."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib
import json
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import main
from records_ui import build_observation_records, render_records_page
from update_notices import validate_notice_config

BASELINE = 'edb77003fb6f648979a10df9efe1e8e010a15e9f'
root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc)
sections = ('research', 'best-shots', 'guide', 'season', 'features')
all_new = {s: 'new' for s in sections}
states = {'off': {}, 'new': all_new, 'identified': {**all_new, 'research': 'identified'},
          'long': all_new, 'both': {'research': 'identified', 'best-shots': 'new'},
          'research-only': {'research': 'new'}, 'best-only': {'best-shots': 'new'}}
portal = json.loads(subprocess.check_output(['git', 'show', 'origin/gh-pages:portal-data.json']))
records = build_observation_records(portal)
grouped = {p['gallery_name']: [] for p in portal['observations']}
for name, mapping in states.items():
    events = [{'section': s, 'kind': k, 'occurred_at': (now - timedelta(hours=1)).isoformat(),
               'summary': (('長い通知文でも画像上の文字は動かしません。' * 4)[:80] if name == 'long'
                           else '1種の正体が判明' if k == 'identified' else '新しい写真を追加')}
              for s, k in mapping.items()]
    validate_notice_config({'version': 1, 'events': events})
    main.OUTPUT_DIR = str(root / name)
    main.load_notice_events = lambda: events
    main.generate_new_top(grouped, {}, records, feature_search_available=True,
                          research_summary={'case_count': 66}, best_shot_summary={'entry_count': 12})
    (root / name / 'records.html').write_text(render_records_page(portal), encoding='utf-8')
# Same reference markup isolates badge CSS changes. Before CSS is the exact published main.
before = subprocess.check_output(['git', 'show', f'{BASELINE}:assets/update-notices.css']).decode()
after = Path('assets/update-notices.css').read_text()
protected = '/* A quiet, periodic sweep:'
assert before[before.index(protected):] == after[after.index(protected):]
(root / 'before.css').write_text(before)
(root / 'after.css').write_text(after)
(root / 'badges.html').write_text('''<!doctype html><meta charset="utf-8"><link id="badge-css" rel="stylesheet" href="before.css">
<style>body{margin:0;padding:24px;background:#f7fcf4;color:#26352b;font:14px sans-serif}h2{font-size:14px;margin:0 0 14px}.samples{display:flex;gap:12px;align-items:center}p{margin:18px 0 0}</style>
<h2 id="label">Before</h2><div class="samples"><span class="update-badge update-badge--new">NEW!</span><span class="update-badge update-badge--identified">IDENTIFIED!</span><span class="update-badge update-badge--update">UPDATE!</span></div>
<p>NEW! · IDENTIFIED! · UPDATE!</p>''', encoding='utf-8')
(root / 'fixture.json').write_text(json.dumps({'baseline': BASELINE, 'now': now.isoformat(),
    'states': list(states), 'notice_counts': {s: len(v) for s, v in states.items()}, 'public_photos': len(portal['observations']),
    'protected_css_sha256': hashlib.sha256(after[after.index(protected):].encode()).hexdigest()}, indent=2))
print('PASS: isolated portal fixtures and byte-identical sheen/delays/reduced-motion block')
