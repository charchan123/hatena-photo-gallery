"""Isolated real portal generator fixtures; never edits production notices/data."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import main
from records_ui import build_observation_records, render_records_page
from update_notices import validate_notice_config

BASELINE = 'edb77003fb6f648979a10df9efe1e8e010a15e9f'
LAYOUT_BASELINE = '9296710aa12053f50c911a9797900eaf35046155'
root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc)
sections = ('research', 'best-shots', 'guide', 'season', 'features')
all_new = {s: 'new' for s in sections}
states = {'off': {}, 'new': all_new, 'identified': {'research': 'identified'},
          'long': all_new, 'both': {'research': 'identified', 'best-shots': 'new'},
          'research-only': {'research': 'new'}, 'best-only': {'best-shots': 'new'},
          'expired': all_new}
portal = json.loads(subprocess.check_output(['git', 'show', 'origin/gh-pages:portal-data.json']))
records = build_observation_records(portal)
grouped = {p['gallery_name']: [] for p in portal['observations']}

def old_generator(ref, name):
    module = types.ModuleType(name)
    module.__file__ = main.__file__
    sys.modules[name] = module
    source = subprocess.check_output(['git', 'show', f'{ref}:main.py']).decode()
    exec(compile(source, main.__file__, 'exec'), module.__dict__)
    return module

before_main = old_generator(LAYOUT_BASELINE, 'notice_layout_before')
published_main = old_generator(BASELINE, 'notice_layout_published')
for name, mapping in states.items():
    events = [{'section': s, 'kind': k,
               'occurred_at': (now - (timedelta(days=15) if name == 'expired' else timedelta(hours=1))).isoformat(),
               'summary': (('長い通知文でも画像上の文字は動かしません。' * 4)[:80] if name == 'long'
                           else '1種の正体が判明' if k == 'identified' else '新しい写真を追加')}
              for s, k in mapping.items()]
    validate_notice_config({'version': 1, 'events': events})
    variants = [(main, root / name, None), (before_main, root / 'before' / name, LAYOUT_BASELINE)]
    if name == 'off':
        variants.append((published_main, root / 'published' / name, BASELINE))
    for generator, output, ref in variants:
        generator.OUTPUT_DIR = str(output)
        generator.load_notice_events = lambda: events
        generator.generate_new_top(grouped, {}, records, feature_search_available=True,
                                   research_summary={'case_count': 66}, best_shot_summary={'entry_count': 12})
        (output / 'records.html').write_text(render_records_page(portal), encoding='utf-8')
        if ref:
            for asset in ('portal.css', 'update-notices.css'):
                (output / 'assets' / asset).write_bytes(subprocess.check_output(['git', 'show', f'{ref}:assets/{asset}']))
# Preserve the entire completed pill stylesheet, not only its sheen definition.
before = subprocess.check_output(['git', 'show', f'{LAYOUT_BASELINE}:assets/update-notices.css']).decode()
after = Path('assets/update-notices.css').read_text()
assert before == after
protected = '/* A quiet, periodic sweep:'
(root / 'before.css').write_text(before)
(root / 'after.css').write_text(after)
(root / 'badges.html').write_text('''<!doctype html><meta charset="utf-8"><link id="badge-css" rel="stylesheet" href="before.css">
<style>body{margin:0;padding:24px;background:#f7fcf4;color:#26352b;font:14px sans-serif}h2{font-size:14px;margin:0 0 14px}.samples{display:flex;gap:12px;align-items:center}p{margin:18px 0 0}</style>
<h2 id="label">Before</h2><div class="samples"><span class="update-badge update-badge--new">NEW!</span><span class="update-badge update-badge--identified">IDENTIFIED!</span><span class="update-badge update-badge--update">UPDATE!</span></div>
<p>NEW! · IDENTIFIED! · UPDATE!</p>''', encoding='utf-8')
(root / 'fixture.json').write_text(json.dumps({'baseline': BASELINE, 'layout_baseline': LAYOUT_BASELINE, 'now': now.isoformat(),
    'states': list(states), 'notice_counts': {s: (0 if s == 'expired' else len(v)) for s, v in states.items()},
    'public_photos': len(portal['observations']), 'badge_css_sha256': hashlib.sha256(after.encode()).hexdigest(),
    'protected_css_sha256': hashlib.sha256(after[after.index(protected):].encode()).hexdigest()}, indent=2))
print('PASS: actual previous/current portal generators; byte-identical entire badge stylesheet')
