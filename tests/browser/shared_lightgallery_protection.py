"""Compare protected source bytes and independent published data; read-only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from lightgallery_css_guard import verify_gallery_css

ROOT = Path(__file__).resolve().parents[2]
MAIN = '8007a72708aff2dfa14e2e9638f44720bb449b76'
BASE = sys.argv[2] if len(sys.argv) > 2 else 'origin/main'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def value(ref, path):
    return json.loads(git('show', f'{ref}:{path}'))

def digest(content):
    return hashlib.sha256(content).hexdigest()

# The PR base includes the separately accepted artwork replacements. Preserve
# those exact bytes rather than comparing current artwork to the old PR #139.
paths = git('ls-tree', '-rz', '--name-only', BASE).decode().split('\0')
mutable = {'assets/gallery.js', 'best_shot_ui.py', 'gallery_dependencies.py'}
protected = [p for p in paths if p and p not in mutable and not p.startswith(
    ('.github/', 'audit/', 'tests/', 'docs/', 'tools/'))]
before = {p: digest(git('show', f'{BASE}:{p}')) for p in protected}
after = {p: digest((ROOT / p).read_bytes()) for p in protected}
gallery_css = 'assets/gallery.css'
viewer_rules_added = verify_gallery_css(git('show', f'{BASE}:{gallery_css}'),
                                        (ROOT / gallery_css).read_bytes())
unexpected = [p for p in protected if p != gallery_css and before[p] != after[p]]
assert not unexpected, unexpected
# The latest main's protected data are independently byte-equal, not only counts.
for p in git('ls-tree', '-rz', '--name-only', MAIN).decode().split('\0'):
    if p.startswith(('data/', 'sync-migrations/', 'admin/', 'comments/', 'hatena/', 'lightgallery/')):
        assert digest(git('show', f'{MAIN}:{p}')) == after[p], p

portal = value('origin/gh-pages', 'portal-data.json')
snapshot = value('origin/gh-pages', 'article-sync-snapshot.json')
comments = value('origin/gh-pages', 'research-comments-config.json')
assert comments['enabled'] is False and comments['api_url'] == ''
source_counts = {
    'best_shots': len(value(MAIN, 'data/best-shots.json')['entries']),
    'annual_best': len(value(MAIN, 'data/best-shots.json')['annual_best']),
    'notices': len(value(MAIN, 'data/update-notices.json')['events']),
    'master': len(value(MAIN, 'data/mushroom-master.json')['entries']),
    'sources': len(value(MAIN, 'data/sources.json')['sources']),
}
published_counts = {
    'photos': len(portal['observations']),
    'research_cases': len(value('origin/gh-pages', 'research-comment-cases.json')['active_ids']),
    'retired': snapshot['payload']['retirement']['retired_count'],
    'master': len(portal['reference_data']['mushroom_master']['entries']),
    'sources': len(portal['reference_data']['sources']['sources']),
}
assert source_counts['master'] == published_counts['master']
assert source_counts['sources'] == published_counts['sources']
from bs4 import BeautifulSoup
published_ids = set()
for p in git('ls-tree', '-rz', '--name-only', 'origin/gh-pages').decode().split('\0'):
    if p.startswith('best-shots-') and p.endswith('.html'):
        soup = BeautifulSoup(git('show', f'origin/gh-pages:{p}'), 'html.parser')
        published_ids.update(card['data-selection-id'] for card in soup.select('[data-selection-id]'))
assert published_ids == {entry['selection_id'] for entry in value(MAIN, 'data/best-shots.json')['entries']}
published_counts['best_shots'] = len(published_ids)
vendor_tree = git('rev-parse', f'{MAIN}:lightgallery').decode().strip()
assert vendor_tree == git('rev-parse', 'origin/gh-pages:lightgallery').decode().strip()
# Preserve actual observation IDs, URLs and EXIF-bearing capture fields as a unit.
output_paths = ['portal-data.json', 'article-sync-snapshot.json', 'research-comment-cases.json',
                'research-comments-config.json']
output_hashes = {p: digest(git('show', f'origin/gh-pages:{p}')) for p in output_paths}
result = {'source_base': git('rev-parse', BASE).decode().strip(), 'historical_data_base': MAIN,
          'main': git('rev-parse', 'origin/main').decode().strip(),
          'published': git('rev-parse', 'origin/gh-pages').decode().strip(),
          'protected_file_count': len(protected), 'protected_sha256': digest(json.dumps(after, sort_keys=True).encode()),
          'before_after_equal': before == after, 'reviewed_gallery_viewer_rules_added': viewer_rules_added,
          'other_protected_sources_equal': not unexpected, 'source_counts': source_counts,
          'published_counts': published_counts, 'published_sha256': output_hashes,
          'critical_source_sha256': {p: after[p] for p in protected if p.startswith('data/')},
          'local_and_published_vendor_tree': vendor_tree, 'comments_enabled': comments['enabled'], 'external_mutations': []}
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
